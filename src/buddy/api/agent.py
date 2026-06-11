"""Endpoints for the PC agent and the Android UsageStats reporter.

Both clients call:
    POST /agent/heartbeat   — submit a foreground/idle report
    GET  /agent/status      — long-poll-style: tells the client whether to
                              keep reporting and which categories are
                              distractors for the active session

Plus configuration:
    POST   /distraction-rules               — add a rule
    GET    /distraction-rules?goal_id=N     — list rules for a goal
    DELETE /distraction-rules/{id}          — remove a rule
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from buddy.auth import require_auth
from buddy.db import get_session_factory
from buddy.models import (
    AgentReport,
    DistractionRule,
    FocusSession,
    Goal,
    Intervention,
)
from buddy.schemas_phase4 import (
    AgentHeartbeat,
    AgentHeartbeatResponse,
    AgentStatusResponse,
    DistractionRuleCreate,
    DistractionRuleOut,
    DistractionRulesListResponse,
)
from buddy.services.interventions import (
    detect_drift_for_session,
    run_engine_tick,
)

router = APIRouter()


@router.post(
    "/agent/heartbeat",
    response_model=AgentHeartbeatResponse,
    dependencies=[Depends(require_auth)],
)
async def agent_heartbeat(req: AgentHeartbeat) -> AgentHeartbeatResponse:
    factory = get_session_factory()
    async with factory() as db:
        active = (
            await db.execute(
                select(FocusSession).where(FocusSession.state == "active")
            )
        ).scalar_one_or_none()
        report = AgentReport(
            session_id=active.id if active else None,
            source=req.source,
            foreground_category=req.foreground_category,
            foreground_app_hint=req.foreground_app_hint,
            idle_seconds=req.idle_seconds,
            active_seconds=req.active_seconds,
            raw_payload=req.raw_payload,
        )
        db.add(report)
        await db.commit()

        drift = False
        if active is not None:
            await db.refresh(report)
            episode = await detect_drift_for_session(db, active)
            drift = episode is not None
            # Run a tick now too, so any escalation is up-to-date when the
            # phone next polls /interventions/pending.
            await run_engine_tick(db)

        pending_count = (
            await db.execute(
                select(Intervention).where(
                    Intervention.dismissed_at.is_(None),
                    Intervention.delivered_at.is_(None),
                )
            )
        ).scalars().all()

    return AgentHeartbeatResponse(
        received=True,
        active_session_id=active.id if active else None,
        interventions_pending=len(pending_count),
        drift_flagged=drift,
    )


@router.get(
    "/agent/status",
    response_model=AgentStatusResponse,
    dependencies=[Depends(require_auth)],
)
async def agent_status() -> AgentStatusResponse:
    """The PC agent calls this every ~10s to learn whether to keep
    reporting and which categories count as distractors right now."""
    factory = get_session_factory()
    async with factory() as db:
        active = (
            await db.execute(
                select(FocusSession).where(FocusSession.state == "active")
            )
        ).scalar_one_or_none()
        if active is None:
            return AgentStatusResponse(
                active_session_id=None,
                intention=None,
                distractor_categories=[],
            )
        if active.goal_id is None:
            return AgentStatusResponse(
                active_session_id=active.id,
                intention=active.intention,
                distractor_categories=[],
            )
        rules = (
            await db.execute(
                select(DistractionRule).where(
                    DistractionRule.goal_id == active.goal_id,
                    DistractionRule.is_active.is_(True),
                )
            )
        ).scalars().all()
    return AgentStatusResponse(
        active_session_id=active.id,
        intention=active.intention,
        distractor_categories=sorted({r.distractor_category for r in rules}),
    )


# --- Distraction rules -----------------------------------------------------


@router.get(
    "/distraction-rules",
    response_model=DistractionRulesListResponse,
    dependencies=[Depends(require_auth)],
)
async def list_distraction_rules(goal_id: int) -> DistractionRulesListResponse:
    factory = get_session_factory()
    async with factory() as db:
        rows = (
            await db.execute(
                select(DistractionRule).where(DistractionRule.goal_id == goal_id)
            )
        ).scalars().all()
    return DistractionRulesListResponse(
        rules=[
            DistractionRuleOut(
                id=r.id,
                goal_id=r.goal_id,
                distractor_category=r.distractor_category,
                cooldown_seconds=r.cooldown_seconds,
                is_active=r.is_active,
            )
            for r in rows
        ]
    )


@router.post(
    "/distraction-rules",
    response_model=DistractionRuleOut,
    dependencies=[Depends(require_auth)],
)
async def create_distraction_rule(req: DistractionRuleCreate) -> DistractionRuleOut:
    factory = get_session_factory()
    async with factory() as db:
        if (await db.get(Goal, req.goal_id)) is None:
            raise HTTPException(404, f"Goal {req.goal_id} not found.")
        row = DistractionRule(
            goal_id=req.goal_id,
            distractor_category=req.distractor_category,
            cooldown_seconds=req.cooldown_seconds,
            is_active=True,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return DistractionRuleOut(
        id=row.id,
        goal_id=row.goal_id,
        distractor_category=row.distractor_category,
        cooldown_seconds=row.cooldown_seconds,
        is_active=row.is_active,
    )


@router.delete(
    "/distraction-rules/{rule_id}",
    dependencies=[Depends(require_auth)],
)
async def delete_distraction_rule(rule_id: int) -> dict:
    factory = get_session_factory()
    async with factory() as db:
        row = await db.get(DistractionRule, rule_id)
        if row is None:
            raise HTTPException(404, "Rule not found.")
        await db.delete(row)
        await db.commit()
    return {"deleted": rule_id}
