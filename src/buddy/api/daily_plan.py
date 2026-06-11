"""Daily-plan endpoints — the "Coach me today" UX path."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from buddy.auth import require_auth
from buddy.db import get_session_factory
from buddy.models import DailyPlan, DailyPlanItem
from buddy.services.daily_plan import apply_item_action, get_or_generate_today

router = APIRouter()


class DailyPlanItemOut(BaseModel):
    id: int
    plan_id: int
    goal_id: int
    task_text: str
    tier: Literal["must", "should", "could"]
    est_minutes: int
    rationale: str
    state: Literal["pending", "done", "deferred", "declined"]
    defer_reason: str
    defer_until: date | None
    defer_context: str
    position: int
    created_at: datetime
    completed_at: datetime | None


class DailyPlanOut(BaseModel):
    id: int
    plan_date: date
    status: str
    rationale: str
    items: list[DailyPlanItemOut]
    created_at: datetime
    updated_at: datetime


class DailyPlanItemActionRequest(BaseModel):
    action: Literal["done", "defer", "decline"]
    reason: str | None = Field(default=None, max_length=2000)


@router.get(
    "/daily-plan/today",
    response_model=DailyPlanOut,
    dependencies=[Depends(require_auth)],
)
async def get_today() -> DailyPlanOut:
    """Returns today's plan, generating it on the first call of the day.

    Idempotent: subsequent calls within the same day return the
    persisted plan unchanged. The Android client hits this on the
    Today screen mount.
    """
    factory = get_session_factory()
    async with factory() as db:
        plan = await get_or_generate_today(db)
        items = await _load_items(db, plan.id)
    return _serialize(plan, items)


@router.post(
    "/daily-plan/items/{item_id}/action",
    response_model=DailyPlanItemOut,
    dependencies=[Depends(require_auth)],
)
async def post_action(
    item_id: int, req: DailyPlanItemActionRequest
) -> DailyPlanItemOut:
    """Apply a user action to a plan item. Free-text reasons get
    parsed for defer-until + context via fast-tier tool-use."""
    factory = get_session_factory()
    async with factory() as db:
        try:
            item = await apply_item_action(
                db, item_id=item_id, action=req.action, reason=req.reason
            )
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
    return _item_to_out(item)


async def _load_items(db, plan_id: int) -> list[DailyPlanItem]:
    from sqlalchemy import select

    rows = await db.execute(
        select(DailyPlanItem)
        .where(DailyPlanItem.plan_id == plan_id)
        .order_by(DailyPlanItem.position.asc(), DailyPlanItem.id.asc())
    )
    return list(rows.scalars().all())


def _item_to_out(item: DailyPlanItem) -> DailyPlanItemOut:
    return DailyPlanItemOut(
        id=item.id,
        plan_id=item.plan_id,
        goal_id=item.goal_id,
        task_text=item.task_text,
        tier=item.tier,  # type: ignore[arg-type]
        est_minutes=item.est_minutes,
        rationale=item.rationale,
        state=item.state,  # type: ignore[arg-type]
        defer_reason=item.defer_reason,
        defer_until=item.defer_until,
        defer_context=item.defer_context,
        position=item.position,
        created_at=item.created_at,
        completed_at=item.completed_at,
    )


def _serialize(plan: DailyPlan, items: list[DailyPlanItem]) -> DailyPlanOut:
    return DailyPlanOut(
        id=plan.id,
        plan_date=plan.plan_date,
        status=plan.status,
        rationale=plan.rationale,
        items=[_item_to_out(i) for i in items],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )
