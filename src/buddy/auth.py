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
    # Both sides get .strip()-ed: protects against a trailing newline that
    # snuck into the .env file or a stray space the client tacked on.
    token = authorization[7:].strip()
    expected = (settings.auth_token or "").strip()
    if not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )
    return True
