"""Capture-anywhere pipeline.

The user dictates (or types) a free-form thought; the fast tier classifies it
into structured actions; we round-trip a confirmation; on confirm we dispatch
each action to the appropriate Phase 0/2 endpoint.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from buddy.auth import require_auth
from buddy.db import get_session_factory
from buddy.llm.client import chat_with_tool
from buddy.llm.tools import CLASSIFY_CAPTURE_TOOL
from buddy.llm.models import ModelTier, resolve_model
from buddy.llm.prompts.capture import CAPTURE_SYSTEM, build_capture_user_message
from buddy.models import (
    ApiUsage,
    CaptureLog,
    FocusSession,
    Goal,
    JournalEntry,
    ProgressLog,
    Task,
)
from buddy.schemas_phase3 import (
    CaptureAction,
    CaptureConfirm,
    CaptureDispatchResponse,
    CaptureRequest,
    CaptureResponse,
    DispatchResultItem,
)

router = APIRouter()


@router.post(
    "/capture", response_model=CaptureResponse, dependencies=[Depends(require_auth)]
)
async def capture(req: CaptureRequest) -> CaptureResponse:
    factory = get_session_factory()
    async with factory() as db:
        active = (
            await db.execute(
                select(Goal).where(Goal.state == "active").order_by(Goal.priority.desc())
            )
        ).scalars().all()

    payload = [
        {
            "goal_id": g.id,
            "statement": g.statement,
            "pace_target_unit": g.pace_target_unit,
            "pace_target_amount": g.pace_target_amount,
        }
        for g in active
    ]
    user_msg = build_capture_user_message(req.text, payload)
    model = resolve_model(ModelTier.FAST)

    try:
        result = await chat_with_tool(
            model=model,
            system=CAPTURE_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
            tool=CLASSIFY_CAPTURE_TOOL,
            max_tokens=1024,
            temperature=0.1,
        )
    except Exception as exc:
        raise HTTPException(502, f"Capture classification failed: {exc}") from exc

    out = result.tool_input

    actions: list[CaptureAction] = []
    for item in out.get("actions") or []:
        try:
            actions.append(
                CaptureAction(
                    kind=str(item.get("kind") or "unknown"),
                    summary=str(item.get("summary") or ""),
                    payload=dict(item.get("payload") or {}),
                    confidence=float(item.get("confidence") or 0.0),
                )
            )
        except Exception:
            continue

    fallback = str(out.get("fallback_message") or "")

    factory = get_session_factory()
    async with factory() as db:
        log = CaptureLog(
            raw_text=req.text,
            proposed_actions=[a.model_dump(mode="json") for a in actions],
            confirmed=False,
            source=req.source,
        )
        db.add(log)
        db.add(
            ApiUsage(
                provider="anthropic",
                model=result.model,
                operation="capture_classify",
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=result.cost_usd,
            )
        )
        await db.commit()
        await db.refresh(log)
        capture_id = log.id

    return CaptureResponse(
        capture_id=capture_id,
        raw_text=req.text,
        actions=actions,
        fallback_message=fallback,
    )


@router.post(
    "/capture/confirm",
    response_model=CaptureDispatchResponse,
    dependencies=[Depends(require_auth)],
)
async def confirm_capture(req: CaptureConfirm) -> CaptureDispatchResponse:
    factory = get_session_factory()
    results: list[DispatchResultItem] = []

    async with factory() as db:
        log = await db.get(CaptureLog, req.capture_id)
        if log is None:
            raise HTTPException(404, "Capture log not found.")

        for action in req.actions:
            try:
                created_id = await _dispatch(db, action)
                results.append(
                    DispatchResultItem(
                        kind=action.kind,
                        success=True,
                        detail=action.summary,
                        created_id=created_id,
                    )
                )
            except DispatchError as exc:
                results.append(
                    DispatchResultItem(
                        kind=action.kind,
                        success=False,
                        detail=str(exc),
                    )
                )

        log.confirmed = True
        log.dispatched_at = datetime.utcnow()
        log.proposed_actions = [a.model_dump(mode="json") for a in req.actions]
        await db.commit()

    return CaptureDispatchResponse(capture_id=req.capture_id, results=results)


# --- Dispatcher ------------------------------------------------------------


class DispatchError(Exception):
    """A specific action failed to dispatch."""


async def _dispatch(db, action: CaptureAction) -> int | None:
    p = action.payload
    if action.kind == "log_progress":
        gid = p.get("goal_id")
        if gid is None:
            raise DispatchError("Missing goal_id.")
        goal = await db.get(Goal, int(gid))
        if goal is None:
            raise DispatchError(f"Goal {gid} not found.")
        units = float(p.get("attributed_units") or 0.0)
        if units <= 0:
            raise DispatchError("attributed_units must be > 0.")
        row = ProgressLog(
            goal_id=int(gid),
            raw_text=str(p.get("raw_text") or action.summary),
            attributed_units=units,
            unit_label=str(p.get("unit_label") or goal.pace_target_unit),
            source="voice",
            confidence=action.confidence,
            note="capture",
        )
        db.add(row)
        await db.flush()
        return row.id

    if action.kind == "create_task":
        gid = p.get("goal_id")
        if gid is None:
            raise DispatchError("Missing goal_id.")
        goal = await db.get(Goal, int(gid))
        if goal is None:
            raise DispatchError(f"Goal {gid} not found.")
        row = Task(
            goal_id=int(gid),
            description=str(p.get("description") or action.summary),
            definition_of_done="",
            estimated_duration_minutes=p.get("estimated_duration_minutes"),
            first_60_seconds=str(p.get("first_60_seconds") or ""),
            state="proposed",
        )
        db.add(row)
        await db.flush()
        return row.id

    if action.kind == "create_goal":
        statement = str(p.get("statement") or "").strip()
        if not statement:
            raise DispatchError("Missing statement.")
        row = Goal(
            statement=statement,
            priority=int(p.get("priority") or 3),
            pace_target_amount=float(p.get("pace_target_amount") or 0.0),
            pace_target_unit=str(p.get("pace_target_unit") or ""),
            mvp_threshold=str(p.get("mvp_threshold") or ""),
            state="active",
            approach="user_driven",
            plan_source="user_plan",
        )
        db.add(row)
        await db.flush()
        return row.id

    if action.kind == "journal_note":
        content = str(p.get("content") or "").strip()
        if not content:
            raise DispatchError("Empty journal content.")
        today = date.today()
        existing = await db.get(JournalEntry, today)
        if existing is None:
            existing = JournalEntry(entry_date=today, content="", mood="", tags=[])
            db.add(existing)
        # Append rather than replace so the user can capture multiple times a day.
        sep = "\n\n" if existing.content else ""
        existing.content = f"{existing.content}{sep}{content}"
        if not existing.mood:
            existing.mood = str(p.get("mood") or "")
        existing.updated_at = datetime.utcnow()
        await db.flush()
        return None

    if action.kind == "start_focus":
        intention = str(p.get("intention") or "").strip()
        if not intention:
            raise DispatchError("Missing intention.")
        # Refuse to start a session if one is already active.
        existing = (
            await db.execute(
                select(FocusSession).where(FocusSession.state == "active")
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise DispatchError(f"Focus session {existing.id} is already active.")
        row = FocusSession(
            goal_id=p.get("goal_id"),
            intention=intention,
            planned_duration_minutes=int(p.get("planned_duration_minutes") or 45),
            state="active",
        )
        db.add(row)
        await db.flush()
        return row.id

    if action.kind == "reminder":
        # Phase 3 placeholder: not implemented as a scheduled job yet, but we
        # store it as a note so the user has a record.
        what = str(p.get("what") or "").strip()
        when = str(p.get("when") or "").strip()
        if not what:
            raise DispatchError("Empty reminder.")
        today = date.today()
        existing = await db.get(JournalEntry, today)
        if existing is None:
            existing = JournalEntry(entry_date=today, content="", mood="", tags=[])
            db.add(existing)
        line = f"[reminder for {when or 'soon'}]: {what}"
        sep = "\n" if existing.content else ""
        existing.content = f"{existing.content}{sep}{line}"
        existing.updated_at = datetime.utcnow()
        await db.flush()
        return None

    if action.kind == "quick_question":
        # Quick questions go through the normal /converse flow on the client.
        return None

    if action.kind == "unknown":
        raise DispatchError("No action attached.")

    raise DispatchError(f"Unsupported action kind: {action.kind}")
