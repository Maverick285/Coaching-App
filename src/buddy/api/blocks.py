"""Blocked-app rule CRUD + the phone's poll-for-active-blocks endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from buddy.auth import require_auth
from buddy.db import get_session_factory
from buddy.models import BlockedAppRule, FocusSession, Goal
from buddy.schemas_phase5 import (
    ActiveBlockOut,
    ActiveBlocksResponse,
    BlockedAppRuleCreate,
    BlockedAppRuleOut,
    BlockedAppRulesListResponse,
)
from buddy.services.overrides import expire_stale, get_active_override

router = APIRouter()


def _to_out(r: BlockedAppRule) -> BlockedAppRuleOut:
    return BlockedAppRuleOut(
        id=r.id,
        goal_id=r.goal_id,
        package_name=r.package_name,
        block_tier=r.block_tier,
        is_active=r.is_active,
    )


@router.get(
    "/blocked-apps",
    response_model=BlockedAppRulesListResponse,
    dependencies=[Depends(require_auth)],
)
async def list_blocked_apps(goal_id: int) -> BlockedAppRulesListResponse:
    factory = get_session_factory()
    async with factory() as db:
        rows = (
            await db.execute(
                select(BlockedAppRule).where(BlockedAppRule.goal_id == goal_id)
            )
        ).scalars().all()
    return BlockedAppRulesListResponse(rules=[_to_out(r) for r in rows])


@router.post(
    "/blocked-apps",
    response_model=BlockedAppRuleOut,
    dependencies=[Depends(require_auth)],
)
async def create_blocked_app(req: BlockedAppRuleCreate) -> BlockedAppRuleOut:
    factory = get_session_factory()
    async with factory() as db:
        if (await db.get(Goal, req.goal_id)) is None:
            raise HTTPException(404, f"Goal {req.goal_id} not found.")
        row = BlockedAppRule(
            goal_id=req.goal_id,
            package_name=req.package_name,
            block_tier=req.block_tier,
            is_active=True,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return _to_out(row)


@router.delete("/blocked-apps/{rule_id}", dependencies=[Depends(require_auth)])
async def delete_blocked_app(rule_id: int) -> dict:
    factory = get_session_factory()
    async with factory() as db:
        row = await db.get(BlockedAppRule, rule_id)
        if row is None:
            raise HTTPException(404, "Rule not found.")
        await db.delete(row)
        await db.commit()
    return {"deleted": rule_id}


@router.get(
    "/blocked-apps/active",
    response_model=ActiveBlocksResponse,
    dependencies=[Depends(require_auth)],
)
async def active_blocks() -> ActiveBlocksResponse:
    """Phone polls this every few seconds during a focus session.
    If an override window is open, returns no blocks."""
    factory = get_session_factory()
    async with factory() as db:
        await expire_stale(db)
        await db.commit()

        active_override = await get_active_override(db)
        if active_override is not None:
            return ActiveBlocksResponse(
                blocks=[],
                override_window_open=True,
                override_expires_at=active_override.expires_at,
            )

        active = (
            await db.execute(
                select(FocusSession).where(FocusSession.state == "active")
            )
        ).scalar_one_or_none()
        if active is None or active.goal_id is None:
            return ActiveBlocksResponse(blocks=[])

        rules = (
            await db.execute(
                select(BlockedAppRule).where(
                    BlockedAppRule.goal_id == active.goal_id,
                    BlockedAppRule.is_active.is_(True),
                )
            )
        ).scalars().all()

    return ActiveBlocksResponse(
        blocks=[
            ActiveBlockOut(
                package_name=r.package_name,
                block_tier=r.block_tier,
                goal_id=r.goal_id,
                session_id=active.id,
            )
            for r in rules
        ]
    )
