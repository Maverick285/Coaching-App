"""Monthly cost circuit-breaker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select

from buddy.config import get_settings
from buddy.db import get_session_factory
from buddy.models import ApiUsage


@dataclass
class UsageBuckets:
    today: float
    month_to_date: float
    last_7_days: float
    today_in: int = 0
    today_out: int = 0
    mtd_in: int = 0
    mtd_out: int = 0
    last7_in: int = 0
    last7_out: int = 0


async def usage_buckets() -> UsageBuckets:
    factory = get_session_factory()
    now = datetime.utcnow()
    start_of_today = datetime(now.year, now.month, now.day)
    start_of_month = datetime(now.year, now.month, 1)
    start_of_last_7 = now - timedelta(days=7)

    async with factory() as session:

        async def _sum(after: datetime) -> tuple[int, int, float]:
            q = select(
                func.coalesce(func.sum(ApiUsage.tokens_in), 0),
                func.coalesce(func.sum(ApiUsage.tokens_out), 0),
                func.coalesce(func.sum(ApiUsage.cost_usd), 0.0),
            ).where(ApiUsage.occurred_at >= after)
            row = (await session.execute(q)).one()
            return int(row[0]), int(row[1]), float(row[2])

        ti, to, tcost = await _sum(start_of_today)
        mi, mo, mcost = await _sum(start_of_month)
        wi, wo, wcost = await _sum(start_of_last_7)

    return UsageBuckets(
        today=tcost,
        month_to_date=mcost,
        last_7_days=wcost,
        today_in=ti,
        today_out=to,
        mtd_in=mi,
        mtd_out=mo,
        last7_in=wi,
        last7_out=wo,
    )


async def enforce_budget() -> None:
    settings = get_settings()
    buckets = await usage_buckets()
    if buckets.month_to_date >= settings.budget_hard_usd:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Hard budget cap exceeded: ${buckets.month_to_date:.2f} of "
                f"${settings.budget_hard_usd:.2f}. Raise BUDDY_BUDGET_HARD_USD or wait "
                "for the next billing cycle."
            ),
        )


async def cap_status() -> tuple[bool, bool]:
    settings = get_settings()
    buckets = await usage_buckets()
    return (
        buckets.month_to_date >= settings.budget_soft_usd,
        buckets.month_to_date >= settings.budget_hard_usd,
    )
