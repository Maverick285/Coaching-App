"""Tier 5 stake-at-risk webhook firing (master spec §13.1)."""

from __future__ import annotations

import asyncio
from datetime import date

import httpx


def _make_active_goal_with_stake(client, url: str) -> int:
    r = client.post(
        "/goals",
        json={
            "statement": "Tier-5 protected goal",
            "priority": 5,
            "stake_webhook_url": url,
            "stake_webhook_secret": "hunter2",
            "stake_active": True,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_floor_check_fires_stake_webhook_for_zero_day(authed_client, monkeypatch):
    fired: list[dict] = []

    class FakeResponse:
        status_code = 200
        text = "ok"

    class FakeClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, url, json, headers):
            fired.append({"url": url, "body": json, "headers": dict(headers)})
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    goal_id = _make_active_goal_with_stake(
        authed_client, "https://example.com/derail"
    )
    # No progress logged today → floor breaks for this goal.
    from buddy.db import get_session_factory
    from buddy.services.interventions import run_floor_check

    async def _run():
        factory = get_session_factory()
        async with factory() as db:
            await run_floor_check(db, day=date.today())

    asyncio.run(_run())
    assert len(fired) == 1
    body = fired[0]["body"]
    assert body["goal_id"] == goal_id
    assert body["event_kind"] == "zero_day_floor_break"
    assert "Bearer hunter2" in fired[0]["headers"]["Authorization"]


def test_stake_does_not_fire_when_inactive(authed_client, monkeypatch):
    fired: list[dict] = []

    class FakeResponse:
        status_code = 200
        text = "ok"

    class FakeClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, url, json, headers):
            fired.append(json)
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    # Create a goal with a webhook configured but stake_active=False
    r = authed_client.post(
        "/goals",
        json={
            "statement": "non-tier-5 goal",
            "priority": 3,
            "stake_webhook_url": "https://example.com/derail",
            "stake_active": False,
        },
    )
    assert r.status_code == 200

    from buddy.db import get_session_factory
    from buddy.services.interventions import run_floor_check

    async def _run():
        factory = get_session_factory()
        async with factory() as db:
            await run_floor_check(db, day=date.today())

    asyncio.run(_run())
    assert fired == []
