"""Intervention endpoints (phone polls these to render Tier 0/1/2 nudges)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from buddy.auth import require_auth
from buddy.db import get_session_factory
from buddy.models import Intervention
from buddy.schemas_phase4 import (
    InterventionAction,
    InterventionOut,
    InterventionsPendingResponse,
)
from buddy.services.interventions import run_engine_tick, run_floor_check

router = APIRouter()


def _to_out(i: Intervention) -> InterventionOut:
    return InterventionOut(
        id=i.id,
        session_id=i.session_id,
        goal_id=i.goal_id,
        tier=i.tier,
        fired_at=i.fired_at,
        delivered_at=i.delivered_at,
        dismissed_at=i.dismissed_at,
        next_escalation_at=i.next_escalation_at,
        reason=i.reason,
        message=i.message,
    )


@router.get(
    "/interventions/pending",
    response_model=InterventionsPendingResponse,
    dependencies=[Depends(require_auth)],
)
async def pending_interventions() -> InterventionsPendingResponse:
    """Phone polls every ~30s during active sessions. Anything fired but
    not yet dismissed shows up here. We also run an engine tick first so
    fresh escalations land in the same response."""
    factory = get_session_factory()
    async with factory() as db:
        await run_engine_tick(db)
        rows = (
            await db.execute(
                select(Intervention)
                .where(Intervention.dismissed_at.is_(None))
                .order_by(Intervention.fired_at.desc())
            )
        ).scalars().all()
    return InterventionsPendingResponse(interventions=[_to_out(r) for r in rows])


@router.post(
    "/interventions/{intervention_id}/action",
    response_model=InterventionOut,
    dependencies=[Depends(require_auth)],
)
async def update_intervention(
    intervention_id: int, req: InterventionAction
) -> InterventionOut:
    factory = get_session_factory()
    async with factory() as db:
        row = await db.get(Intervention, intervention_id)
        if row is None:
            raise HTTPException(404, "Intervention not found.")
        now = datetime.utcnow()
        if req.action == "delivered" and row.delivered_at is None:
            row.delivered_at = now
        if req.action == "dismissed":
            row.dismissed_at = now
            # Clear the escalation pointer so the engine's grace-period
            # check distinguishes user dismissal from tier supersession.
            row.next_escalation_at = None
        await db.commit()
        await db.refresh(row)
    return _to_out(row)


@router.post(
    "/interventions/floor-check",
    response_model=InterventionsPendingResponse,
    dependencies=[Depends(require_auth)],
)
async def trigger_floor_check() -> InterventionsPendingResponse:
    """Manually run the daily floor check (also runs on the scheduled job)."""
    factory = get_session_factory()
    async with factory() as db:
        fired = await run_floor_check(db)
    return InterventionsPendingResponse(interventions=[_to_out(f) for f in fired])
