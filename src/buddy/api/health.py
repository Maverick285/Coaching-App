"""Liveness endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from buddy import __version__
from buddy.config import get_settings
from buddy.db import get_session_factory
from buddy.llm.models import resolve_all_tiers
from buddy.memory.store import MemoryStore
from buddy.schemas import DailyRhythm, HealthResponse

router = APIRouter()


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
    )
