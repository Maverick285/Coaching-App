"""SQLAlchemy async engine + session factory, plus sqlite-vec loading."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sqlite_vec
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from buddy.config import get_settings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
VEC_AVAILABLE: bool = False  # set true by _try_load_vec on first successful connect.


class Base(DeclarativeBase):
    pass


def _try_load_sync(raw: sqlite3.Connection) -> bool:
    try:
        raw.enable_load_extension(True)
        sqlite_vec.load(raw)
        raw.enable_load_extension(False)
        return True
    except Exception:
        return False


def _enable_sqlite_extensions(dbapi_conn, _conn_record) -> None:
    """Load sqlite-vec on every new connection so vec0 virtual tables work.

    Works for both raw sqlite3 connections and SQLAlchemy's aiosqlite adapter.
    """
    global VEC_AVAILABLE

    # Path 1: raw sqlite3 (sync engine, tests).
    if isinstance(dbapi_conn, sqlite3.Connection):
        if _try_load_sync(dbapi_conn):
            VEC_AVAILABLE = True
        return

    # Path 2: SQLAlchemy's AsyncAdapt_aiosqlite_connection wraps an aiosqlite
    # connection in `.driver_connection`, which itself wraps the real sqlite3
    # Connection in `._conn`. The real Connection lives in a worker thread,
    # but `enable_load_extension` is safe to call from the main thread because
    # SQLite serializes access internally for the default threading mode.
    try:
        driver = getattr(dbapi_conn, "driver_connection", None) or dbapi_conn
        raw = getattr(driver, "_conn", None) or driver
        if isinstance(raw, sqlite3.Connection) and _try_load_sync(raw):
            VEC_AVAILABLE = True
    except Exception:
        # Vector search degrades; BM25 still works.
        pass


def get_engine():
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(
            settings.db_url,
            future=True,
            echo=False,
            connect_args={"check_same_thread": False},
        )
        event.listen(_engine.sync_engine, "connect", _enable_sqlite_extensions)
        _session_factory = async_sessionmaker(
            _engine, expire_on_commit=False, class_=AsyncSession
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
