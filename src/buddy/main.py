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


async def _detect_orphaned_schema() -> bool:
    """Detect the 'tables exist but no alembic_version row' state.

    This happens when an earlier factory reset deleted alembic_version
    along with everything else, or when the DB was bootstrapped via
    Base.metadata.create_all (e.g. tests). In both cases the schema is
    actually at head; alembic just doesn't know that. Returns True so
    the caller stamps head before running upgrade.
    """
    from sqlalchemy import inspect, text

    from buddy.db import get_engine

    try:
        engine = get_engine()
        async with engine.begin() as conn:
            tables = await conn.run_sync(
                lambda sync_conn: set(inspect(sync_conn).get_table_names())
            )
            if "alembic_version" not in tables or "goals" not in tables:
                # Legitimately empty DB or pre-Phase-2 — let alembic
                # create from scratch.
                return False
            row = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            return row.scalar_one_or_none() is None
    except Exception as exc:  # noqa: BLE001
        log.warn("startup.alembic_orphan_detect_failed", error=str(exc)[:200])
        return False


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
    Refusing to start because of a migration glitch locks the user out
    of the backend entirely (Caddy returns 502 because uvicorn never
    bound) — strictly worse than serving with a stale schema and
    surfacing actionable errors on affected endpoints. /health exposes
    the live schema status so the user can see what happened.

    Two-step path:
      1. If `alembic_version` exists but is empty AND core tables are
         already there, stamp head. This unsticks DBs orphaned by an
         earlier factory reset that wiped the version row.
      2. Run `alembic upgrade head` as usual.
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

    if await _detect_orphaned_schema():
        log.info("startup.alembic_stamping_head_to_recover_orphan")
        rc, _, err = await _run_alembic(
            ["-c", str(ini), "stamp", "head"], cwd=str(repo_root)
        )
        if rc != 0:
            log.error("startup.alembic_stamp_failed", code=rc, stderr=err[-500:])
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
    async def http_exception_handler(_: Request, exc: StarletteHTTPException):
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

    return app


app = create_app()
