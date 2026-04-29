"""Admin endpoints — currently just a hard reset.

Intended for "give me a clean slate" — wipes user state without touching
secrets. Anthropic key, BUDDY_AUTH_TOKEN, and BUDDY_GIT_REMOTE come from
the environment, not the database, so they are unaffected. We do clear
the in-DB preferences table (user_name / persona_name / chat_tier
defaults) so the next launch routes back into onboarding.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from buddy.auth import require_auth
from buddy.db import Base, get_session_factory
from buddy.memory.index import reconcile_index
from buddy.memory.store import MemoryStore

router = APIRouter()


class AdminResetRequest(BaseModel):
    confirm: str


class AdminResetResponse(BaseModel):
    cleared_tables: list[str]
    cleared_files: list[str]


# Tables whose rows we keep across a factory reset.
#
# `alembic_version` is here because deleting it puts alembic into an
# unbootstrappable state on the next launch: it sees "no version row"
# → tries to migrate from base → hits "table goals already exists" →
# fails. We're wiping data, not the schema's identity.
PRESERVE_ROWS_IN: set[str] = {"alembic_version"}


@router.post(
    "/admin/reset",
    response_model=AdminResetResponse,
    dependencies=[Depends(require_auth)],
)
async def admin_reset(req: AdminResetRequest) -> AdminResetResponse:
    if req.confirm != "RESET":
        raise HTTPException(
            400,
            "To confirm, send {\"confirm\": \"RESET\"}. This wipes user data.",
        )

    cleared_tables: list[str] = []
    factory = get_session_factory()
    async with factory() as db:
        # Iterate in reverse dependency order. SQLAlchemy doesn't track
        # implicit FK constraints across all our tables, but on SQLite the
        # foreign-key enforcement is off by default, so plain DELETEs are
        # safe in any order.
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in PRESERVE_ROWS_IN:
                continue
            await db.execute(text(f"DELETE FROM {table.name}"))
            cleared_tables.append(table.name)
        # Also clear the embedding index helper tables that aren't in the
        # ORM (they're created via raw DDL in memory/index.py).
        for raw in (
            "document_chunks_fts",
            "document_chunks_vec",
        ):
            try:
                await db.execute(text(f"DELETE FROM {raw}"))
                cleared_tables.append(raw)
            except Exception:  # noqa: BLE001 - missing table is fine
                pass
        await db.commit()

    # Wipe the memory directory contents and let MemoryStore reseed from
    # SEED_FILES. The directory itself + git repo we keep so file watchers,
    # backup pushes, and existing references stay sane.
    store = MemoryStore()
    cleared_files: list[str] = []
    for child in store.root.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
            cleared_files.append(child.name + "/")
        else:
            child.unlink()
            cleared_files.append(child.name)

    # Recreate the standard subdirs + reseed PERSONA.md / MEMORY.md / etc.
    fresh = MemoryStore()
    fresh._git_commit_all("admin: factory reset — fresh seed")  # noqa: SLF001
    await reconcile_index()

    return AdminResetResponse(
        cleared_tables=cleared_tables,
        cleared_files=cleared_files,
    )
