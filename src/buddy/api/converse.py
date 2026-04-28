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
from buddy.llm.client import chat
from buddy.llm.models import ModelTier, resolve_model
from buddy.llm.prompts.persona import build_persona_system_prompt, render_goals_block
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

    # Detect an active focus session — used by the boundary-detection
    # logic to disable proactive surfacing while the user is in flow.
    from buddy.models import FocusSession
    from sqlalchemy import select as _select
    async with factory() as db:
        active_focus_row = (
            await db.execute(
                _select(FocusSession).where(FocusSession.state == "active").limit(1)
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

    try:
        result = await chat(
            model=model,
            system=system_prompt,
            messages=messages,
            max_tokens=2048 if tier is ModelTier.REASONING else 1024,
            temperature=0.7,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc

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
    )


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
