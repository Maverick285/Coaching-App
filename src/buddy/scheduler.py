"""APScheduler setup for nightly consolidation, periodic index reconciliation,
budget checks, and memory-repo backup pushes.
"""

from __future__ import annotations

from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from buddy.config import get_settings
from buddy.db import get_session_factory
from buddy.logging_setup import get_logger
from buddy.memory.consolidation import run_consolidation
from buddy.memory.index import reconcile_index
from buddy.memory.store import MemoryStore
from buddy.services.budget import cap_status
from buddy.services.grading import compute_day_grade, upsert_day_grade
from buddy.services.interventions import run_engine_tick, run_floor_check

log = get_logger("buddy.scheduler")
_scheduler: AsyncIOScheduler | None = None


async def _consolidation_job() -> None:
    log.info("scheduler.consolidation.start")
    result = await run_consolidation()
    log.info("scheduler.consolidation.done", **result)


async def _reconcile_job() -> None:
    result = await reconcile_index()
    if result["indexed"] or result["removed"]:
        log.info("scheduler.reconcile", **result)


async def _budget_job() -> None:
    soft, hard = await cap_status()
    if soft or hard:
        log.warn("scheduler.budget", soft_exceeded=soft, hard_exceeded=hard)


async def _backup_push_job() -> None:
    settings = get_settings()
    if not settings.git_remote:
        return
    status = MemoryStore().push_to_remote()
    log.info("scheduler.backup_push", status=status)


async def _day_grade_precompute_job() -> None:
    """Compute today's grade so it's instant when the user opens the app at end-of-day."""
    today = datetime.utcnow().date()
    factory = get_session_factory()
    async with factory() as db:
        result = await compute_day_grade(db, today)
        await upsert_day_grade(db, result)
        await db.commit()
    log.info(
        "scheduler.day_grade",
        date=str(today),
        score=result.system_score,
        zero=result.is_zero_day,
    )


async def _intervention_engine_tick_job() -> None:
    """Drift detection + tier escalation, every 30 seconds."""
    factory = get_session_factory()
    async with factory() as db:
        result = await run_engine_tick(db)
    if result.drift_fired or result.floor_fired:
        log.info(
            "scheduler.engine_tick",
            drift=len(result.drift_fired),
            floor=len(result.floor_fired),
        )


async def _floor_check_job() -> None:
    """Daily floor-check: any active goal with no progress today gets a
    Tier 0 nudge. Runs at the user's configured end-of-day hour."""
    factory = get_session_factory()
    async with factory() as db:
        fired = await run_floor_check(db)
    if fired:
        log.info("scheduler.floor_check", fired=len(fired))


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    settings = get_settings()
    sched = AsyncIOScheduler(timezone=settings.timezone)

    sched.add_job(
        _consolidation_job,
        CronTrigger(hour=settings.consolidation_hour, minute=0, timezone=settings.timezone),
        id="consolidation",
        replace_existing=True,
    )
    sched.add_job(
        _reconcile_job,
        IntervalTrigger(seconds=30),
        id="reconcile",
        replace_existing=True,
    )
    sched.add_job(
        _budget_job,
        CronTrigger(hour=8, minute=0, timezone=settings.timezone),
        id="budget_check",
        replace_existing=True,
    )
    sched.add_job(
        _backup_push_job,
        CronTrigger(hour=settings.consolidation_hour, minute=15, timezone=settings.timezone),
        id="backup_push",
        replace_existing=True,
    )
    sched.add_job(
        _day_grade_precompute_job,
        CronTrigger(
            hour=settings.end_of_day_hour,
            minute=settings.end_of_day_minute,
            timezone=settings.timezone,
        ),
        id="day_grade_precompute",
        replace_existing=True,
    )
    sched.add_job(
        _intervention_engine_tick_job,
        IntervalTrigger(seconds=30),
        id="intervention_engine_tick",
        replace_existing=True,
    )
    sched.add_job(
        _floor_check_job,
        CronTrigger(
            hour=settings.end_of_day_hour,
            minute=(settings.end_of_day_minute + 1) % 60,
            timezone=settings.timezone,
        ),
        id="floor_check",
        replace_existing=True,
    )

    sched.start()
    _scheduler = sched
    log.info("scheduler.started", jobs=[j.id for j in sched.get_jobs()])
    return sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
