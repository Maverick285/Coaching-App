"""Daily journal endpoints (one entry per day)."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from buddy.auth import require_auth
from buddy.db import get_session_factory
from buddy.models import JournalEntry
from buddy.schemas_phase2 import (
    JournalEntryOut,
    JournalEntryWrite,
    JournalListResponse,
)

router = APIRouter()


def _to_out(j: JournalEntry) -> JournalEntryOut:
    return JournalEntryOut(
        entry_date=j.entry_date,
        content=j.content,
        mood=j.mood,
        tags=list(j.tags or []),
        created_at=j.created_at,
        updated_at=j.updated_at,
    )


@router.get(
    "/journal",
    response_model=JournalListResponse,
    dependencies=[Depends(require_auth)],
)
async def list_journal(limit: int = 30) -> JournalListResponse:
    factory = get_session_factory()
    async with factory() as db:
        rows = (
            await db.execute(
                select(JournalEntry).order_by(JournalEntry.entry_date.desc()).limit(limit)
            )
        ).scalars().all()
    return JournalListResponse(entries=[_to_out(r) for r in rows])


@router.get(
    "/journal/{day}",
    response_model=JournalEntryOut,
    dependencies=[Depends(require_auth)],
)
async def get_journal(day: date) -> JournalEntryOut:
    factory = get_session_factory()
    async with factory() as db:
        row = await db.get(JournalEntry, day)
        if row is None:
            return JournalEntryOut(
                entry_date=day,
                content="",
                mood="",
                tags=[],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
    return _to_out(row)


@router.put(
    "/journal/{day}",
    response_model=JournalEntryOut,
    dependencies=[Depends(require_auth)],
)
async def upsert_journal(day: date, req: JournalEntryWrite) -> JournalEntryOut:
    factory = get_session_factory()
    async with factory() as db:
        row = await db.get(JournalEntry, day)
        now = datetime.utcnow()
        if row is None:
            row = JournalEntry(
                entry_date=day,
                content=req.content,
                mood=req.mood,
                tags=req.tags,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
        else:
            row.content = req.content
            row.mood = req.mood
            row.tags = req.tags
            row.updated_at = now
        await db.commit()
        await db.refresh(row)
    return _to_out(row)


@router.delete("/journal/{day}", dependencies=[Depends(require_auth)])
async def delete_journal(day: date) -> dict:
    factory = get_session_factory()
    async with factory() as db:
        row = await db.get(JournalEntry, day)
        if row is None:
            raise HTTPException(404, "No journal entry for that day.")
        await db.delete(row)
        await db.commit()
    return {"deleted": day.isoformat()}
