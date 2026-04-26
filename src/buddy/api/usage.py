"""API usage and budget visibility."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from buddy.auth import require_auth
from buddy.config import get_settings
from buddy.db import get_session_factory
from buddy.models import ApiUsage
from buddy.schemas import UsageBucket, UsageResponse
from buddy.services.budget import usage_buckets

router = APIRouter()


@router.get("/usage", response_model=UsageResponse, dependencies=[Depends(require_auth)])
async def get_usage() -> UsageResponse:
    settings = get_settings()
    buckets = await usage_buckets()

    factory = get_session_factory()
    async with factory() as db:
        by_model_rows = (
            await db.execute(
                select(
                    ApiUsage.model,
                    func.coalesce(func.sum(ApiUsage.tokens_in), 0),
                    func.coalesce(func.sum(ApiUsage.tokens_out), 0),
                    func.coalesce(func.sum(ApiUsage.cost_usd), 0.0),
                ).group_by(ApiUsage.model)
            )
        ).all()

    by_model = [
        UsageBucket(
            label=row[0],
            tokens_in=int(row[1]),
            tokens_out=int(row[2]),
            cost_usd=float(row[3]),
        )
        for row in by_model_rows
    ]

    return UsageResponse(
        today=UsageBucket(
            label="today",
            tokens_in=buckets.today_in,
            tokens_out=buckets.today_out,
            cost_usd=buckets.today,
        ),
        month_to_date=UsageBucket(
            label="month_to_date",
            tokens_in=buckets.mtd_in,
            tokens_out=buckets.mtd_out,
            cost_usd=buckets.month_to_date,
        ),
        last_7_days=UsageBucket(
            label="last_7_days",
            tokens_in=buckets.last7_in,
            tokens_out=buckets.last7_out,
            cost_usd=buckets.last_7_days,
        ),
        by_model=by_model,
        soft_cap_usd=settings.budget_soft_usd,
        hard_cap_usd=settings.budget_hard_usd,
        soft_cap_exceeded=buckets.month_to_date >= settings.budget_soft_usd,
        hard_cap_exceeded=buckets.month_to_date >= settings.budget_hard_usd,
    )
