"""Override-request lifecycle: create → SMS → redeem → time-window."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from buddy.config import get_settings
from buddy.models import OverrideRequest
from buddy.services.sms import get_sender


def _generate_code() -> str:
    """6-digit numeric code. Easy to read aloud over the phone, hard to
    accidentally type, more than enough entropy for a single-use 15-min
    window."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _build_sms_body(
    *, code: str, package: str, reason: str, user_name: str, persona_name: str
) -> str:
    return (
        f"{user_name} is asking {persona_name} to override the block on "
        f"{package or 'an app'}.\n\n"
        f"Reason: {reason or '(no reason given)'}\n\n"
        f"If you approve, the code is: {code}\n\n"
        "Reply only verbally — Buddy doesn't read replies."
    )


async def create_override_request(
    session: AsyncSession,
    *,
    package_name: str,
    reason: str,
    user_name: str,
    persona_name: str,
    session_id: int | None = None,
    goal_id: int | None = None,
    intervention_id: int | None = None,
    active_minutes: int = 15,
) -> OverrideRequest:
    settings = get_settings()
    code = _generate_code()
    sender = get_sender()
    body = _build_sms_body(
        code=code,
        package=package_name,
        reason=reason,
        user_name=user_name,
        persona_name=persona_name,
    )
    sms = sender.send(to=settings.override_approver_number or "(unset)", body=body)

    row = OverrideRequest(
        session_id=session_id,
        goal_id=goal_id,
        intervention_id=intervention_id,
        package_name=package_name,
        reason=reason,
        code=code,
        approver_label=settings.override_approver_label,
        sms_status=sms.status,
        sms_detail=sms.detail,
        status="pending",
        active_minutes=active_minutes,
    )
    session.add(row)
    await session.flush()
    return row


async def redeem_override(
    session: AsyncSession, request_id: int, code: str
) -> tuple[OverrideRequest, bool, str]:
    row = await session.get(OverrideRequest, request_id)
    if row is None:
        raise LookupError(f"Override request {request_id} not found.")
    now = datetime.utcnow()

    if row.status == "approved":
        # Already redeemed; idempotent success if the window is still open.
        if row.expires_at and row.expires_at > now:
            return row, True, "Override is already active."
        row.status = "expired"
        return row, False, "Override window has expired."

    if row.status in ("expired", "rejected"):
        return row, False, f"Override is {row.status}."

    if code.strip() != row.code:
        return row, False, "Code did not match."

    row.status = "approved"
    row.redeemed_at = now
    row.expires_at = now + timedelta(minutes=row.active_minutes)
    await session.flush()
    return row, True, "Override active."


async def get_active_override(session: AsyncSession) -> OverrideRequest | None:
    """Returns the most recently approved override whose window is still
    open, or None. Used by the engine and the phone's block poll to
    suppress blocks during the override window."""
    now = datetime.utcnow()
    rows = await session.execute(
        select(OverrideRequest)
        .where(
            OverrideRequest.status == "approved",
            OverrideRequest.expires_at.is_not(None),
            OverrideRequest.expires_at > now,
        )
        .order_by(OverrideRequest.expires_at.desc())
    )
    return rows.scalars().first()


async def expire_stale(session: AsyncSession) -> int:
    """Mark approved overrides whose window has passed as 'expired'.
    Called from the scheduler tick + before the phone polls blocks."""
    now = datetime.utcnow()
    rows = await session.execute(
        select(OverrideRequest).where(
            OverrideRequest.status == "approved",
            OverrideRequest.expires_at.is_not(None),
            OverrideRequest.expires_at <= now,
        )
    )
    count = 0
    for r in rows.scalars().all():
        r.status = "expired"
        count += 1
    if count:
        await session.flush()
    return count
