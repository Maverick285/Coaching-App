"""Focus-session endpoints (Phase 3 body-doubling mode).

Lifecycle:
  - /focus/start          — begin a session (max one active at a time)
  - /focus/active         — return the currently active session, if any
  - /focus/{id}           — full detail with check-ins
  - /focus/{id}/check-in  — generate a fresh check-in via the fast tier and persist it
  - /focus/{id}/end       — close out the session and write a summary
  - /focus/recent         — list recent sessions for review
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from buddy.auth import require_auth
from buddy.db import get_session_factory
from buddy.llm.client import chat
from buddy.llm.models import ModelTier, resolve_model
from buddy.llm.prompts.capture import (
    FOCUS_CHECK_IN_SYSTEM,
    build_focus_check_in_user_message,
)
from buddy.memory.store import MemoryStore
from buddy.models import ApiUsage, FocusCheckIn, FocusSession, Goal
from buddy.schemas_phase3 import (
    FocusActiveResponse,
    FocusCheckInOut,
    FocusCheckInResponse,
    FocusCheckInUserReply,
    FocusEnd,
    FocusSessionDetail,
    FocusSessionOut,
    FocusStart,
)

router = APIRouter()


def _to_session_out(s: FocusSession) -> FocusSessionOut:
    return FocusSessionOut(
        id=s.id,
        goal_id=s.goal_id,
        intention=s.intention,
        started_at=s.started_at,
        planned_duration_minutes=s.planned_duration_minutes,
        ended_at=s.ended_at,
        state=s.state,  # type: ignore[arg-type]
        summary=s.summary,
        interventions_fired=s.interventions_fired,
    )


def _to_check_in_out(c: FocusCheckIn) -> FocusCheckInOut:
    return FocusCheckInOut(
        id=c.id,
        session_id=c.session_id,
        fired_at=c.fired_at,
        kind=c.kind,  # type: ignore[arg-type]
        message=c.message,
        user_response=c.user_response,
    )


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    return cleaned


@router.post("/focus/start", response_model=FocusSessionOut, dependencies=[Depends(require_auth)])
async def start_focus(req: FocusStart) -> FocusSessionOut:
    factory = get_session_factory()
    async with factory() as db:
        existing = (
            await db.execute(
                select(FocusSession).where(FocusSession.state == "active")
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(409, f"Focus session {existing.id} is already active.")
        if req.goal_id is not None:
            if (await db.get(Goal, req.goal_id)) is None:
                raise HTTPException(404, f"Goal {req.goal_id} not found.")
        session = FocusSession(
            goal_id=req.goal_id,
            intention=req.intention,
            planned_duration_minutes=req.planned_duration_minutes,
            state="active",
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
    return _to_session_out(session)


@router.post(
    "/focus/{session_id}/end",
    response_model=FocusSessionOut,
    dependencies=[Depends(require_auth)],
)
async def end_focus(session_id: int, req: FocusEnd) -> FocusSessionOut:
    factory = get_session_factory()
    async with factory() as db:
        session = await db.get(FocusSession, session_id)
        if session is None:
            raise HTTPException(404, "Focus session not found.")
        session.state = req.state
        session.summary = req.summary
        session.ended_at = datetime.utcnow()
        await db.commit()
        await db.refresh(session)
    return _to_session_out(session)


@router.get(
    "/focus/active",
    response_model=FocusActiveResponse,
    dependencies=[Depends(require_auth)],
)
async def active_focus() -> FocusActiveResponse:
    factory = get_session_factory()
    async with factory() as db:
        session = (
            await db.execute(
                select(FocusSession)
                .where(FocusSession.state == "active")
                .order_by(FocusSession.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    return FocusActiveResponse(session=_to_session_out(session) if session else None)


@router.get(
    "/focus/recent",
    response_model=list[FocusSessionOut],
    dependencies=[Depends(require_auth)],
)
async def recent_focus(limit: int = 20) -> list[FocusSessionOut]:
    factory = get_session_factory()
    async with factory() as db:
        rows = (
            await db.execute(
                select(FocusSession).order_by(FocusSession.started_at.desc()).limit(limit)
            )
        ).scalars().all()
    return [_to_session_out(s) for s in rows]


@router.get(
    "/focus/{session_id}",
    response_model=FocusSessionDetail,
    dependencies=[Depends(require_auth)],
)
async def get_focus(session_id: int) -> FocusSessionDetail:
    factory = get_session_factory()
    async with factory() as db:
        session = await db.get(FocusSession, session_id)
        if session is None:
            raise HTTPException(404, "Focus session not found.")
        check_ins = (
            await db.execute(
                select(FocusCheckIn)
                .where(FocusCheckIn.session_id == session_id)
                .order_by(FocusCheckIn.fired_at.asc())
            )
        ).scalars().all()
    return FocusSessionDetail(
        session=_to_session_out(session),
        check_ins=[_to_check_in_out(c) for c in check_ins],
    )


@router.post(
    "/focus/{session_id}/check-in",
    response_model=FocusCheckInResponse,
    dependencies=[Depends(require_auth)],
)
async def fire_check_in(
    session_id: int,
    kind: str = "presence",
) -> FocusCheckInResponse:
    """Generate a fresh check-in via the fast tier and persist it."""
    if kind not in {"presence", "mid", "end", "drift"}:
        raise HTTPException(400, f"Invalid check-in kind: {kind}")

    factory = get_session_factory()
    async with factory() as db:
        session = await db.get(FocusSession, session_id)
        if session is None:
            raise HTTPException(404, "Focus session not found.")
        if session.state != "active":
            raise HTTPException(400, "Session is not active.")

        elapsed = max(0, int((datetime.utcnow() - session.started_at).total_seconds() // 60))
        remaining = max(0, session.planned_duration_minutes - elapsed)

    persona_md = ""
    try:
        store = MemoryStore()
        if store.exists("PERSONA.md"):
            persona_md = store.read("PERSONA.md")
    except Exception:
        persona_md = ""

    user_msg = build_focus_check_in_user_message(
        persona_md=persona_md,
        intention=session.intention,
        elapsed_minutes=elapsed,
        remaining_minutes=remaining,
        kind=kind,
    )
    model = resolve_model(ModelTier.FAST)
    try:
        result = await chat(
            model=model,
            system=FOCUS_CHECK_IN_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=256,
            temperature=0.5,
        )
    except Exception as exc:
        raise HTTPException(502, f"Check-in generation failed: {exc}") from exc

    try:
        out = json.loads(_strip_fences(result.text))
        message = str(out.get("message") or "").strip()
    except json.JSONDecodeError:
        # Fall back to the raw text if the model didn't emit JSON.
        message = result.text.strip()

    if not message:
        message = "Still here." if kind == "presence" else "Time check."

    factory = get_session_factory()
    async with factory() as db:
        check_in = FocusCheckIn(
            session_id=session_id,
            kind=kind,
            message=message,
        )
        db.add(check_in)
        db.add(
            ApiUsage(
                provider="anthropic",
                model=result.model,
                operation=f"focus_check_in:{kind}",
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=result.cost_usd,
            )
        )
        await db.commit()
        await db.refresh(check_in)

    return FocusCheckInResponse(check_in=_to_check_in_out(check_in))


@router.post(
    "/focus/check-in/{check_in_id}/reply",
    response_model=FocusCheckInOut,
    dependencies=[Depends(require_auth)],
)
async def check_in_reply(
    check_in_id: int, req: FocusCheckInUserReply
) -> FocusCheckInOut:
    factory = get_session_factory()
    async with factory() as db:
        row = await db.get(FocusCheckIn, check_in_id)
        if row is None:
            raise HTTPException(404, "Check-in not found.")
        row.user_response = req.response
        await db.commit()
        await db.refresh(row)
    return _to_check_in_out(row)
