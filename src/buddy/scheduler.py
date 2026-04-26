"""APScheduler setup for nightly consolidation, periodic index reconciliation,
budget checks, and memory-repo backup pushes.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from buddy.config import get_settings
from buddy.logging_setup import get_logger
from buddy.memory.consolidation import run_consolidation
from buddy.memory.index import reconcile_index
from buddy.memory.store import MemoryStore
from buddy.services.budget import cap_status

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

    sched.start()
    _scheduler = sched
    log.info("scheduler.started", jobs=[j.id for j in sched.get_jobs()])
    return sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
