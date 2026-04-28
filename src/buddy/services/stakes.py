"""Tier 5 stake-at-risk webhook firing.

Master spec §13.1: "Pre-committed financial or social stake activates.
Opt-in per goal; not on by default. Implementation: backend triggers
via webhook (Beeminder API or similar)."

A goal opts into Tier 5 by setting stake_webhook_url + stake_active.
When the engine determines a tier-5-worthy event has occurred (zero day
on a stake-active goal, by default), we POST a small JSON envelope to
the configured URL. The result is recorded in stake_events for audit.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from buddy.db import get_session_factory
from buddy.logging_setup import get_logger
from buddy.models import Goal, StakeEvent

log = get_logger("stakes")


async def fire_stake_webhook(
    *,
    goal_id: int,
    event_kind: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> bool:
    """Fire the tier-5 webhook for `goal_id` if it's opted-in. Returns
    True if a webhook was actually invoked. Failures are logged and
    persisted to stake_events but never raised to the caller —
    intervention engine progress shouldn't depend on third-party uptime.
    """
    factory = get_session_factory()
    async with factory() as db:
        goal = await db.get(Goal, goal_id)
        if goal is None or not goal.stake_active or not goal.stake_webhook_url:
            return False

        body = {
            "goal_id": goal.id,
            "goal_statement": goal.statement,
            "event_kind": event_kind,
            "fired_at": datetime.utcnow().isoformat() + "Z",
            "payload": payload or {},
        }
        headers = {"Content-Type": "application/json"}
        if goal.stake_webhook_secret:
            # Bearer-style header so Beeminder/IFTTT/Zapier can verify.
            headers["Authorization"] = f"Bearer {goal.stake_webhook_secret}"

        status: int | None = None
        body_text = ""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    goal.stake_webhook_url, json=body, headers=headers
                )
                status = resp.status_code
                body_text = resp.text[:1000]
        except Exception as exc:
            body_text = f"exception: {exc}"
            log.warn("stakes.webhook_failed", goal_id=goal.id, error=str(exc))
        else:
            log.info("stakes.webhook_fired", goal_id=goal.id, status=status)

        await _record(
            db,
            goal_id=goal.id,
            event_kind=event_kind,
            payload=body,
            response_status=status,
            response_body=body_text,
        )
        await db.commit()
    return True


async def _record(
    db: AsyncSession,
    *,
    goal_id: int,
    event_kind: str,
    payload: dict[str, Any],
    response_status: int | None,
    response_body: str,
) -> None:
    db.add(
        StakeEvent(
            goal_id=goal_id,
            event_kind=event_kind,
            payload=payload,
            response_status=response_status,
            response_body=response_body,
            fired_at=datetime.utcnow(),
        )
    )


async def goals_with_active_stake(db: AsyncSession) -> list[Goal]:
    rows = await db.execute(
        select(Goal).where(Goal.state == "active", Goal.stake_active.is_(True))
    )
    return list(rows.scalars().all())
