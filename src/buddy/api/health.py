"""Liveness endpoint + diagnostics block.

`/health` is intentionally still cheap — DB ping, memory repo state,
resolved models. The diagnostics block is small (a few preference reads
+ a scheduler dump) so the same endpoint serves both purposes; clients
that want bare liveness can ignore the `diagnostics` field.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from buddy import __version__
from buddy.config import get_settings
from buddy.db import get_session_factory
from buddy.llm.models import resolve_all_tiers
from buddy.memory.store import MemoryStore
from buddy.schemas import DailyRhythm, DiagnosticsBlock, HealthResponse, ScheduledJob
from buddy.services.profile import (
    KEY_LAST_BACKUP_PUSH_AT,
    KEY_LAST_BACKUP_PUSH_STATUS,
    KEY_LAST_CONSOLIDATION_AT,
    KEY_LAST_CONSOLIDATION_STATUS,
    KEY_LAST_ENGINE_TICK_AT,
    KEY_LAST_ENGINE_TICK_FIRED,
    get_pref,
)

router = APIRouter()


async def _build_diagnostics() -> DiagnosticsBlock:
    settings = get_settings()
    factory = get_session_factory()
    async with factory() as db:
        last_cons_at = await get_pref(db, KEY_LAST_CONSOLIDATION_AT)
        last_cons_status = await get_pref(db, KEY_LAST_CONSOLIDATION_STATUS)
        last_backup_at = await get_pref(db, KEY_LAST_BACKUP_PUSH_AT)
        last_backup_status = await get_pref(db, KEY_LAST_BACKUP_PUSH_STATUS)
        last_tick_at = await get_pref(db, KEY_LAST_ENGINE_TICK_AT)
        last_tick_fired = await get_pref(db, KEY_LAST_ENGINE_TICK_FIRED)

    jobs: list[ScheduledJob] = []
    try:
        from buddy.scheduler import _scheduler  # noqa: PLC0415 — runtime introspection only

        if _scheduler is not None:
            for job in _scheduler.get_jobs():
                next_run = job.next_run_time.isoformat() if job.next_run_time else None
                jobs.append(
                    ScheduledJob(
                        id=job.id,
                        next_run_at=next_run,
                        trigger=str(job.trigger),
                    )
                )
    except Exception:
        # Scheduler not started (e.g. unit-test path).
        jobs = []

    return DiagnosticsBlock(
        last_consolidation_at=last_cons_at,
        last_consolidation_status=last_cons_status,
        last_backup_push_at=last_backup_at,
        last_backup_push_status=last_backup_status,
        last_engine_tick_at=last_tick_at,
        last_engine_tick_fired=last_tick_fired,
        sms_configured=settings.sms_configured,
        git_remote_configured=bool(settings.git_remote),
        scheduled_jobs=jobs,
    )


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_ok = True
    try:
        factory = get_session_factory()
        async with factory() as s:
            await s.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    try:
        store = MemoryStore()
        repo_status = store.repo_status()
    except Exception as exc:  # noqa: BLE001
        repo_status = f"error: {exc}"

    try:
        models = resolve_all_tiers()
    except Exception as exc:  # noqa: BLE001
        models = {"error": str(exc)}

    overall = "ok" if db_ok and not repo_status.startswith("error") else "degraded"

    settings = get_settings()
    rhythm = DailyRhythm(
        timezone=settings.timezone,
        morning_hour=settings.morning_check_in_hour,
        morning_minute=settings.morning_check_in_minute,
        end_of_day_hour=settings.end_of_day_hour,
        end_of_day_minute=settings.end_of_day_minute,
    )

    return HealthResponse(
        status=overall,  # type: ignore[arg-type]
        version=__version__,
        db_connected=db_ok,
        memory_repo_status=repo_status,
        models_resolved=models,
        daily_rhythm=rhythm,
        diagnostics=await _build_diagnostics(),
    )
