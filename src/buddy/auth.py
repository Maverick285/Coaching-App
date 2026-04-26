"""Bearer-token auth dependency."""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from buddy.config import get_settings


async def require_auth(authorization: str | None = Header(default=None)) -> bool:
    settings = get_settings()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )
    token = authorization[7:].strip()
    if not secrets.compare_digest(token, settings.auth_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )
    return True
