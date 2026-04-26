"""User-profile preferences with sensible env-var fallbacks.

This module is the only thing the persona prompt and the rest of the
backend should call to learn the user's name / persona name / timezone.
It checks the `preferences` table first; if a key isn't set, it falls
back to the Settings (env-var) value.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from buddy.config import get_settings
from buddy.db import get_session_factory
from buddy.models import Preference

# Known preference keys.
KEY_USER_NAME = "user_name"
KEY_PERSONA_NAME = "persona_name"
KEY_TIMEZONE = "timezone"
KEY_ONBOARDING_COMPLETED_AT = "onboarding_completed_at"


async def get_pref(session: AsyncSession, key: str) -> str | None:
    row = await session.get(Preference, key)
    return row.value if row is not None else None


async def set_pref(session: AsyncSession, key: str, value: str) -> Preference:
    row = await session.get(Preference, key)
    if row is None:
        row = Preference(key=key, value=value, updated_at=datetime.utcnow())
        session.add(row)
    else:
        row.value = value
        row.updated_at = datetime.utcnow()
    await session.flush()
    return row


async def resolve_user_name(session: AsyncSession | None = None) -> str:
    settings = get_settings()
    if session is not None:
        v = await get_pref(session, KEY_USER_NAME)
        if v:
            return v
        return settings.user_name
    factory = get_session_factory()
    async with factory() as s:
        v = await get_pref(s, KEY_USER_NAME)
    return v or settings.user_name


async def resolve_persona_name(session: AsyncSession | None = None) -> str:
    settings = get_settings()
    if session is not None:
        v = await get_pref(session, KEY_PERSONA_NAME)
        if v:
            return v
        return settings.persona_name
    factory = get_session_factory()
    async with factory() as s:
        v = await get_pref(s, KEY_PERSONA_NAME)
    return v or settings.persona_name


async def resolve_timezone(session: AsyncSession | None = None) -> str:
    settings = get_settings()
    if session is not None:
        v = await get_pref(session, KEY_TIMEZONE)
        if v:
            return v
        return settings.timezone
    factory = get_session_factory()
    async with factory() as s:
        v = await get_pref(s, KEY_TIMEZONE)
    return v or settings.timezone


async def is_onboarded() -> bool:
    factory = get_session_factory()
    async with factory() as s:
        v = await get_pref(s, KEY_ONBOARDING_COMPLETED_AT)
    return bool(v)


async def mark_onboarded() -> None:
    factory = get_session_factory()
    async with factory() as s:
        await set_pref(s, KEY_ONBOARDING_COMPLETED_AT, datetime.utcnow().isoformat())
        await s.commit()
