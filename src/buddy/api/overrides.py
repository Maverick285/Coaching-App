"""Override request endpoints — initiate, status, redeem.

Per spec §6.4 + §2.6: friction is the point. The Tier 3/4 block is in
your way; you ask the approver for a code; you enter the code; the
block lifts for `active_minutes`. The system logs everything for
weekly review.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from buddy.auth import require_auth
from buddy.config import get_settings
from buddy.db import get_session_factory
from buddy.models import OverrideRequest
from buddy.schemas_phase5 import (
    OverrideRedeemRequest,
    OverrideRedeemResponse,
    OverrideRequestCreate,
    OverrideRequestOut,
)
from buddy.services.overrides import (
    create_override_request,
    expire_stale,
    redeem_override,
)
from buddy.services.profile import resolve_persona_name, resolve_user_name

router = APIRouter()


def _to_out(row: OverrideRequest, *, include_code: bool = False) -> OverrideRequestOut:
    return OverrideRequestOut(
        id=row.id,
        requested_at=row.requested_at,
        session_id=row.session_id,
        goal_id=row.goal_id,
        intervention_id=row.intervention_id,
        package_name=row.package_name,
        reason=row.reason,
        approver_label=row.approver_label,
        sms_status=row.sms_status,
        sms_detail=row.sms_detail,
        status=row.status,  # type: ignore[arg-type]
        redeemed_at=row.redeemed_at,
        expires_at=row.expires_at,
        active_minutes=row.active_minutes,
        code_dev_echo=(row.code if include_code else None),
    )


@router.post(
    "/overrides",
    response_model=OverrideRequestOut,
    dependencies=[Depends(require_auth)],
)
async def request_override(req: OverrideRequestCreate) -> OverrideRequestOut:
    settings = get_settings()
    factory = get_session_factory()
    async with factory() as db:
        row = await create_override_request(
            db,
            package_name=req.package_name,
            reason=req.reason,
            user_name=await resolve_user_name(db),
            persona_name=await resolve_persona_name(db),
            session_id=req.session_id,
            goal_id=req.goal_id,
            intervention_id=req.intervention_id,
            active_minutes=req.active_minutes,
        )
        await db.commit()
        await db.refresh(row)
    # Echo the code only when SMS isn't configured (dev mode).
    return _to_out(row, include_code=not settings.sms_configured)


@router.get(
    "/overrides/{override_id}",
    response_model=OverrideRequestOut,
    dependencies=[Depends(require_auth)],
)
async def get_override(override_id: int) -> OverrideRequestOut:
    factory = get_session_factory()
    async with factory() as db:
        row = await db.get(OverrideRequest, override_id)
        if row is None:
            raise HTTPException(404, "Override request not found.")
    return _to_out(row, include_code=not get_settings().sms_configured)


@router.post(
    "/overrides/{override_id}/redeem",
    response_model=OverrideRedeemResponse,
    dependencies=[Depends(require_auth)],
)
async def redeem(override_id: int, req: OverrideRedeemRequest) -> OverrideRedeemResponse:
    factory = get_session_factory()
    async with factory() as db:
        try:
            row, success, message = await redeem_override(db, override_id, req.code)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        await db.commit()
        await db.refresh(row)
    return OverrideRedeemResponse(
        request=_to_out(row, include_code=not get_settings().sms_configured),
        success=success,
        message=message,
    )


@router.get(
    "/overrides",
    response_model=list[OverrideRequestOut],
    dependencies=[Depends(require_auth)],
)
async def list_overrides(limit: int = 50) -> list[OverrideRequestOut]:
    """Recent overrides — used by the weekly review and the user's own
    audit. Always excludes the code."""
    factory = get_session_factory()
    async with factory() as db:
        await expire_stale(db)
        await db.commit()
        rows = (
            await db.execute(
                select(OverrideRequest)
                .order_by(OverrideRequest.requested_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    return [_to_out(r, include_code=False) for r in rows]
