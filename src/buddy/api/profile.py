"""User-profile endpoints — runtime-mutable name/persona/timezone.

These are intentionally separate from MEMORY.md (which is the persona's
knowledge of the user) and from PERSONA.md (which is the persona's
behavior). The fields here are operational labels: what the persona
calls itself, what the persona calls you, what timezone the alarms
should fire in.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from buddy.auth import require_auth
from buddy.db import get_session_factory
from buddy.memory.store import MemoryStore
from buddy.schemas import ProfileResponse, ProfileUpdate
from buddy.services.profile import (
    KEY_CHAT_TIER,
    KEY_PERSONA_NAME,
    KEY_TIMEZONE,
    KEY_USER_NAME,
    is_onboarded,
    resolve_chat_tier,
    resolve_persona_name,
    resolve_timezone,
    resolve_user_name,
    set_pref,
)

router = APIRouter()


def _persona_md_is_seed(content: str) -> bool:
    return "_Run the intake to generate this file." in content


def _memory_md_is_seed(content: str) -> bool:
    return "_This file is empty until the persona calibration intake runs._" in content


@router.get(
    "/profile",
    response_model=ProfileResponse,
    dependencies=[Depends(require_auth)],
)
async def get_profile() -> ProfileResponse:
    factory = get_session_factory()
    async with factory() as db:
        user = await resolve_user_name(db)
        persona = await resolve_persona_name(db)
        tz = await resolve_timezone(db)
        chat_tier = await resolve_chat_tier(db)

    store = MemoryStore()
    has_persona = False
    has_memory = False
    if store.exists("PERSONA.md"):
        has_persona = not _persona_md_is_seed(store.read("PERSONA.md"))
    if store.exists("MEMORY.md"):
        has_memory = not _memory_md_is_seed(store.read("MEMORY.md"))

    return ProfileResponse(
        user_name=user,
        persona_name=persona,
        timezone=tz,
        onboarding_complete=await is_onboarded(),
        has_persona_md=has_persona,
        has_memory_md=has_memory,
        chat_tier=chat_tier,  # type: ignore[arg-type]
    )


@router.put(
    "/profile",
    response_model=ProfileResponse,
    dependencies=[Depends(require_auth)],
)
async def update_profile(req: ProfileUpdate) -> ProfileResponse:
    factory = get_session_factory()
    async with factory() as db:
        if req.user_name is not None:
            await set_pref(db, KEY_USER_NAME, req.user_name.strip())
        if req.persona_name is not None:
            await set_pref(db, KEY_PERSONA_NAME, req.persona_name.strip())
        if req.timezone is not None:
            await set_pref(db, KEY_TIMEZONE, req.timezone.strip())
        if req.chat_tier is not None:
            await set_pref(db, KEY_CHAT_TIER, req.chat_tier)
        await db.commit()
    return await get_profile()
