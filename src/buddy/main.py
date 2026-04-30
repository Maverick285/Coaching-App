"""FastAPI app entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from buddy import __version__
from buddy.api import agent as agent_api
from buddy.api import admin as admin_api
from buddy.api import blocks as blocks_api
from buddy.api import capture as capture_api
from buddy.api import conversations as conversations_api
from buddy.api import converse as converse_api
from buddy.api import daily_plan as daily_plan_api
from buddy.api import focus as focus_api
from buddy.api import goal_planner as goal_planner_api
from buddy.api import goals as goals_api
from buddy.api import grade as grade_api
from buddy.api import health as health_api
from buddy.api import intake as intake_api
from buddy.api import interventions as interventions_api
from buddy.api import journal as journal_api
from buddy.api import memory as memory_api
from buddy.api import overrides as overrides_api
from buddy.api import profile as profile_api
from buddy.api import progress as progress_api
from buddy.api import tasks_nl as tasks_nl_api
from buddy.api import usage as usage_api
from buddy.logging_setup import configure_logging, get_logger
from buddy.memory.index import reconcile_index
from buddy.memory.store import MemoryStore
from buddy.scheduler import shutdown_scheduler, start_scheduler

log = get_logger("buddy")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("startup.begin", version=__version__)

    # Bootstrap the memory directory + git repo + seed files.
    MemoryStore()

    # Bring the database schema up to head before anything queries it.
    # This is what most production deploys forget; the symptom is
    # mysterious 500s on routes whose ORM models reference columns the
    # DB doesn't have yet. Running on every boot is safe — alembic is
    # idempotent and noops when already current.
    await _ensure_schema_current()

    # Bring the search index in sync with the markdown files.
    await reconcile_index()

    # Start the background scheduler.
    start_scheduler()

    log.info("startup.ready")
    try:
        yield
    finally:
        log.info("shutdown.begin")
        shutdown_scheduler()
        log.info("shutdown.complete")


# Marker -> latest revision that introduces it. Used by the orphan-
# recovery path to figure out what version a DB is *actually* at when
# alembic_version is missing/empty (e.g. after a factory reset wiped
# it). The list is in order — the latest matching marker wins.
#
#   stake_events table          -> 0007_tier5_stake
#   blocked_app_rules table     -> 0006_phase5
#   preferences table           -> 0005_preferences
#   interventions table         -> 0004_phase4
#   focus_sessions table        -> 0003_phase3
#   goals table                 -> 0002_phase2
#   indexed_documents table     -> 0001_initial
#
# We also check the stake_webhook_url column on goals as a finer
# discriminator for 0007 — the original first-pass migration left
# some prod DBs with the column added but stake_events not created
# (or the index missing). Treat any of those signals as "at 0007".
_MARKER_REVISIONS: list[tuple[str, str]] = [
    ("stake_events", "0007_tier5_stake"),
    ("blocked_app_rules", "0006_phase5"),
    ("preferences", "0005_preferences"),
    ("interventions", "0004_phase4"),
    ("focus_sessions", "0003_phase3"),
    ("goals", "0002_phase2"),
    ("indexed_documents", "0001_initial"),
]


async def _detect_actual_revision() -> str | None:
    """Inspect the live schema and return the highest revision the
    schema markers match. None means the DB is empty or pre-Phase-2.

    This is the source of truth — alembic_version may *lie* (e.g. an
    earlier bad stamp set it to 0007 when the schema was at 0006),
    so we always reconcile against what the tables actually look like.
    """
    from sqlalchemy import inspect

    from buddy.db import get_engine

    try:
        engine = get_engine()
        async with engine.begin() as conn:
            tables = await conn.run_sync(
                lambda c: set(inspect(c).get_table_names())
            )
            if "goals" not in tables:
                return None
            goals_cols = await conn.run_sync(
                lambda c: {col["name"] for col in inspect(c).get_columns("goals")}
            )
            # 0007 needs *both* the new column and the new table —
            # otherwise the stamp is wrong and we should pretend we're
            # at 0006 so upgrade head will apply it.
            if "stake_webhook_url" in goals_cols and "stake_events" in tables:
                return "0007_tier5_stake"
            for marker_table, rev in _MARKER_REVISIONS:
                if marker_table == "stake_events":
                    continue  # already handled above
                if marker_table in tables:
                    return rev
            return "0001_initial"
    except Exception as exc:  # noqa: BLE001
        log.warn("startup.schema_detect_failed", error=str(exc)[:200])
        return None


async def _read_alembic_version() -> str | None:
    """Returns the value of alembic_version.version_num, or None if
    the table doesn't exist / has no row / read fails."""
    from sqlalchemy import inspect, text

    from buddy.db import get_engine

    try:
        engine = get_engine()
        async with engine.begin() as conn:
            tables = await conn.run_sync(
                lambda c: set(inspect(c).get_table_names())
            )
            if "alembic_version" not in tables:
                return None
            row = await conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            )
            return row.scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001
        log.warn("startup.alembic_version_read_failed", error=str(exc)[:200])
        return None


async def _run_alembic(args: list[str], cwd: str) -> tuple[int, str, str]:
    """Run `alembic <args>` in cwd; return (returncode, stdout, stderr)."""
    import asyncio

    try:
        proc = await asyncio.create_subprocess_exec(
            "alembic", *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode(errors="ignore"),
            stderr.decode(errors="ignore"),
        )
    except Exception as exc:  # noqa: BLE001
        return (-1, "", f"invocation failed: {exc}")


async def _ensure_schema_current() -> None:
    """Bring the database schema up to head before the app serves.

    Best-effort: any failure logs loud and lets the app come up anyway.

    Three-step path:
      1. Detect what revision the schema *actually* matches by
         inspecting tables/columns.
      2. Compare to the alembic_version value. If they disagree (or
         alembic_version is empty), stamp the *real* revision. This
         repairs DBs broken by my earlier bug that stamped head
         without checking whether the schema was at head.
      3. Run `alembic upgrade head` to apply anything still pending.
    """
    import shutil
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    ini = repo_root / "alembic.ini"
    if not ini.exists():
        log.warn("startup.alembic_ini_missing", path=str(ini))
        return
    if shutil.which("alembic") is None:
        log.warn("startup.alembic_binary_missing")
        return

    actual = await _detect_actual_revision()
    recorded = await _read_alembic_version()

    log.info(
        "startup.alembic_state",
        actual_schema=actual,
        recorded_version=recorded,
    )

    if actual is not None and actual != recorded:
        log.info(
            "startup.alembic_reconcile_stamp",
            from_=recorded or "(none)",
            to=actual,
        )
        rc, _, err = await _run_alembic(
            ["-c", str(ini), "stamp", actual], cwd=str(repo_root)
        )
        if rc != 0:
            log.error(
                "startup.alembic_stamp_failed", revision=actual, stderr=err[-500:]
            )
            return

    rc, _, err = await _run_alembic(
        ["-c", str(ini), "upgrade", "head"], cwd=str(repo_root)
    )
    if rc != 0:
        log.error("startup.alembic_upgrade_failed", code=rc, stderr=err[-2000:])
        return
    log.info("startup.alembic_upgrade_ok")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Buddy",
        version=__version__,
        description="Personal AI companion backend (Phase 0).",
        lifespan=lifespan,
    )

    app.include_router(health_api.router)
    app.include_router(intake_api.router)
    app.include_router(converse_api.router)
    app.include_router(memory_api.router)
    app.include_router(conversations_api.router)
    app.include_router(usage_api.router)
    # Phase 2 routes.
    app.include_router(goals_api.router)
    app.include_router(goal_planner_api.router)
    app.include_router(tasks_nl_api.router)
    app.include_router(progress_api.router)
    app.include_router(grade_api.router)
    app.include_router(daily_plan_api.router)
    app.include_router(journal_api.router)
    # Phase 3 routes.
    app.include_router(capture_api.router)
    app.include_router(focus_api.router)
    # Phase 4 routes.
    app.include_router(agent_api.router)
    app.include_router(interventions_api.router)
    # Customization: profile + onboarding state.
    app.include_router(profile_api.router)
    # Phase 5: blocked-app rules + override system.
    app.include_router(blocks_api.router)
    app.include_router(overrides_api.router)
    # Admin: factory reset.
    app.include_router(admin_api.router)

    # Auth-debug middleware: logs the last-6 chars of every incoming
    # Authorization: Bearer header alongside the path. Helps diagnose
    # token-mismatch vs missing-header bugs from real clients. Cheap
    # enough to leave on at personal-use volume.
    @app.middleware("http")
    async def log_auth_header(request: Request, call_next):
        auth = request.headers.get("authorization") or ""
        tail = "(none)"
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            tail = f"len={len(token)} ...{token[-6:]}" if token else "(empty)"
        elif auth:
            tail = f"raw='{auth[:20]}...'"
        log.info("auth.debug", path=request.url.path, token=tail)
        return await call_next(request)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        # Capture 5xx HTTPExceptions (the 502s the planner throws) too.
        if exc.status_code >= 500:
            from buddy.services.error_log import record as record_error
            record_error(
                method=request.method,
                path=request.url.path,
                exc=exc,
                status=exc.status_code,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "http_error", "detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        """Catch every unhandled exception, persist to the ring buffer
        so the user can see the real traceback from /admin/errors, and
        return a structured 500 with the exception class + message.
        """
        from buddy.services.error_log import record as record_error
        record_error(
            method=request.method,
            path=request.url.path,
            exc=exc,
            status=500,
        )
        log.error(
            "unhandled_exception",
            method=request.method,
            path=request.url.path,
            exception=f"{type(exc).__name__}: {exc}",
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "detail": f"{type(exc).__name__}: {exc}",
                "hint": "GET /admin/errors for the traceback.",
            },
        )

    return app


app = create_app()
