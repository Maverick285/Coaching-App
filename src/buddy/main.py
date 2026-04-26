"""FastAPI app entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from buddy import __version__
from buddy.api import agent as agent_api
from buddy.api import capture as capture_api
from buddy.api import conversations as conversations_api
from buddy.api import converse as converse_api
from buddy.api import focus as focus_api
from buddy.api import goals as goals_api
from buddy.api import grade as grade_api
from buddy.api import health as health_api
from buddy.api import intake as intake_api
from buddy.api import interventions as interventions_api
from buddy.api import journal as journal_api
from buddy.api import memory as memory_api
from buddy.api import progress as progress_api
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
    app.include_router(progress_api.router)
    app.include_router(grade_api.router)
    app.include_router(journal_api.router)
    # Phase 3 routes.
    app.include_router(capture_api.router)
    app.include_router(focus_api.router)
    # Phase 4 routes.
    app.include_router(agent_api.router)
    app.include_router(interventions_api.router)

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
