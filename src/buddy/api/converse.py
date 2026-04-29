"""The /converse endpoint: the primary conversational path.

For each call we:
  1. Look up or create the session.
  2. Assemble the memory context (always-loaded + retrieved).
  3. Build the persona system prompt from PERSONA.md + retrieved.
  4. Route to the appropriate LLM tier.
  5. Persist the user message and the assistant response.
  6. Append the exchange to the on-disk conversation log.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text

from buddy.auth import require_auth
from buddy.config import get_settings
from buddy.db import get_session_factory
from buddy.llm.client import chat, chat_with_optional_tools
from buddy.llm.models import ModelTier, resolve_model
from buddy.llm.prompts.persona import build_persona_system_prompt, render_goals_block
from buddy.llm.tools import LOG_PROGRESS_INLINE_TOOL, PROPOSE_GOAL_INLINE_TOOL
from buddy.models import FocusSession, Goal, ProgressLog
from buddy.llm.router import select_tier
from buddy.memory.retrieval import assemble_context
from buddy.memory.store import MemoryStore
from buddy.models import ApiUsage, Conversation, ConversationMessage
from buddy.schemas import ConverseRequest, ConverseResponse, MemoryLoadedItem
from buddy.services.budget import enforce_budget
from buddy.services.grading import active_goals, progress_for_goal

router = APIRouter()

CONVERSATION_HISTORY_TURNS = 12


@router.post("/converse", response_model=ConverseResponse, dependencies=[Depends(require_auth)])
async def converse(req: ConverseRequest) -> ConverseResponse:
    settings = get_settings()
    await enforce_budget()

    session_id = req.session_id or uuid.uuid4().hex
    factory = get_session_factory()

    # 1. Load (or create) session and prior turns.
    async with factory() as db:
        existing = await db.get(Conversation, session_id)
        if existing is None:
            existing = Conversation(
                session_id=session_id,
                started_at=datetime.utcnow(),
                last_message_at=datetime.utcnow(),
                title="",
            )
            db.add(existing)
            await db.commit()

        rows = (
            await db.execute(
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.created_at.desc())
                .limit(CONVERSATION_HISTORY_TURNS)
            )
        ).scalars().all()
        history = list(reversed(rows))

    # 2. Assemble memory context + load active goals with today's progress.
    store = MemoryStore()
    ctx = await assemble_context(user_message=req.message, store=store)

    today = datetime.utcnow().date()
    async with factory() as db:
        goals = await active_goals(db)
        goals_with_progress = [
            (g, await progress_for_goal(db, g.id, today)) for g in goals
        ]
    goals_block = render_goals_block(goals_with_progress)

    # 3. Build the persona system prompt with resolved profile fields.
    from buddy.services.profile import (
        resolve_chat_tier,
        resolve_persona_name,
        resolve_timezone,
        resolve_user_name,
    )

    user_name = await resolve_user_name()
    persona_name = await resolve_persona_name()
    timezone = await resolve_timezone()
    chat_tier_pref = await resolve_chat_tier()

    # Active-focus state gates proactive surfacing — the persona stays
    # quiet while the user is mid-flow regardless of clock-time.
    async with factory() as db:
        active_focus_row = (
            await db.execute(
                select(FocusSession).where(FocusSession.state == "active").limit(1)
            )
        ).scalar_one_or_none()
    has_active_focus = active_focus_row is not None

    system_prompt = build_persona_system_prompt(
        retrieved=ctx,
        user_name=user_name,
        persona_name=persona_name,
        timezone=timezone,
        goals_block=goals_block,
        boundary_context=req.boundary_context,
        active_focus=has_active_focus,
    )

    # 4. Route + call. The user's chat_tier preference pins the tier unless
    # they've explicitly forced reasoning on this turn.
    tier = select_tier(message=req.message, force_reasoning=req.force_reasoning_tier)
    if not req.force_reasoning_tier:
        if chat_tier_pref == "reasoning":
            tier = ModelTier.REASONING
        elif chat_tier_pref == "fast":
            tier = ModelTier.FAST
    model = resolve_model(tier)

    messages: list[dict] = [
        {"role": m.role, "content": m.content} for m in history if m.role in ("user", "assistant")
    ]
    messages.append({"role": "user", "content": req.message})

    # Offer the persona a small set of inline tools (master spec §47).
    # The model can choose to text-respond, propose a goal, log
    # progress against an existing goal, or do both. We auto-execute
    # the low-stakes ones (log_progress) and surface the high-stakes
    # ones (propose_goal) as confirmable cards.
    chat_tools = [PROPOSE_GOAL_INLINE_TOOL, LOG_PROGRESS_INLINE_TOOL]
    try:
        tool_result = await chat_with_optional_tools(
            model=model,
            system=system_prompt,
            messages=messages,
            tools=chat_tools,
            max_tokens=2048 if tier is ModelTier.REASONING else 1024,
            temperature=0.7,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc

    # Bridge layer: turn the model's tool_use blocks into either
    # already-executed actions (low-stakes) or proposals returned to the
    # client (high-stakes for user confirmation).
    proposed_actions: list[dict] = []
    executed_actions: list[dict] = []
    response_text = tool_result.text or ""

    for call in tool_result.tool_calls:
        if call.name == "log_progress":
            executed = await _auto_log_progress(call.input)
            executed_actions.append(executed)
            # Append a short ack to the persona's text so the user
            # always sees confirmation of what got logged. Some models
            # emit only the tool call without prose.
            if executed.get("ok"):
                ack = (
                    f"\n\n_Logged {executed['amount']:g} {executed['unit']} "
                    f"on \"{executed['goal_statement']}\"._"
                )
                response_text = response_text + ack if response_text else ack.strip()
            else:
                response_text += f"\n\n_Tried to log progress but {executed.get('error', 'failed')}._"
        elif call.name == "propose_goal":
            proposed_actions.append({"kind": "propose_goal", "payload": call.input})

    # Synthesize a default text if the model emitted only a tool_use
    # with no prose — otherwise the chat bubble would be empty.
    if not response_text:
        if proposed_actions:
            response_text = "I drafted a goal — confirm below to save it."
        else:
            response_text = "(empty response)"

    # Re-shape into the same fields as the old chat() result so the
    # downstream persistence path doesn't have to fork.
    class _Shim:
        pass
    result = _Shim()
    result.text = response_text
    result.model = tool_result.model
    result.tokens_in = tool_result.tokens_in
    result.tokens_out = tool_result.tokens_out
    result.cost_usd = tool_result.cost_usd

    # 5. Persist user + assistant turns and the usage row.
    user_msg_id = uuid.uuid4().hex
    assistant_msg_id = uuid.uuid4().hex
    memory_loaded_serialized = ctx.summary_for_response()

    async with factory() as db:
        db.add(
            ConversationMessage(
                id=user_msg_id,
                session_id=session_id,
                role="user",
                content=req.message,
                model_used="",
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                memory_loaded=[],
            )
        )
        db.add(
            ConversationMessage(
                id=assistant_msg_id,
                session_id=session_id,
                role="assistant",
                content=result.text,
                model_used=result.model,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=result.cost_usd,
                memory_loaded=memory_loaded_serialized,
            )
        )
        db.add(
            ApiUsage(
                provider="anthropic",
                model=result.model,
                operation=f"converse:{tier.value}",
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=result.cost_usd,
            )
        )
        # Update last_message_at and (lazily) title.
        await db.execute(
            text(
                "UPDATE conversations SET last_message_at = :ts, "
                "title = CASE WHEN title = '' THEN :title ELSE title END "
                "WHERE session_id = :sid"
            ),
            {
                "ts": datetime.utcnow(),
                "title": req.message[:80],
                "sid": session_id,
            },
        )
        await db.commit()

    # 6. Append to the on-disk conversation log.
    _append_log(store, session_id, req.message, result.text, model)

    return ConverseResponse(
        session_id=session_id,
        message_id=assistant_msg_id,
        response=result.text,
        model_used=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_estimate=result.cost_usd,
        memory_loaded=[MemoryLoadedItem(**item) for item in memory_loaded_serialized],
        proposed_actions=proposed_actions,
        executed_actions=executed_actions,
    )


async def _auto_log_progress(payload: dict) -> dict:
    """Persist a ProgressLog row from a model-emitted log_progress
    tool call. Returns a small descriptor the API includes in
    executed_actions so the client can show what was logged.

    Low-stakes per master spec §44.5: execute on tool call, undo
    available. We validate the goal_id against the current active set
    so the model can't fabricate a goal_id and successfully insert.
    """
    try:
        goal_id = int(payload.get("goal_id", 0))
        amount = float(payload.get("amount", 0.0))
    except (TypeError, ValueError) as exc:
        return {"ok": False, "error": f"invalid payload: {exc}"}
    if goal_id <= 0 or amount <= 0:
        return {"ok": False, "error": "goal_id and amount must be positive"}
    unit = str(payload.get("unit") or "").strip()
    notes = str(payload.get("notes") or "").strip()

    factory = get_session_factory()
    async with factory() as db:
        goal = await db.get(Goal, goal_id)
        if goal is None or goal.state != "active":
            return {"ok": False, "error": f"goal_id={goal_id} not active"}
        log_row = ProgressLog(
            goal_id=goal_id,
            raw_text=notes or f"Logged via chat: {amount:g} {unit}",
            attributed_units=amount,
            unit_label=unit,
            source="chat",
            confidence=0.95,
        )
        db.add(log_row)
        await db.commit()
        await db.refresh(log_row)
    return {
        "ok": True,
        "kind": "log_progress",
        "log_id": log_row.id,
        "goal_id": goal_id,
        "goal_statement": goal.statement,
        "amount": amount,
        "unit": unit,
    }


def _append_log(
    store: MemoryStore,
    session_id: str,
    user_message: str,
    assistant_message: str,
    model: str,
) -> None:
    today = datetime.now().date().isoformat()
    short = session_id[:8]
    rel = store.conversation_log_path(today, short)
    ts = datetime.now().strftime("%H:%M:%S")
    block = (
        f"\n## {ts} — user\n\n{user_message.strip()}\n"
        f"\n## {ts} — {model}\n\n{assistant_message.strip()}\n"
    )
    if not store.exists(rel):
        header = f"# Conversation {short} — {today}\n"
        store.write(rel, header + block, commit_message=f"log: open {rel}")
    else:
        store.append(rel, block, commit_message=f"log: append {rel}")
