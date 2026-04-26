"""Drift detection + tier 0/1/2 escalation + floor check."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest


def _make_active_session_with_rule(client, *, distractor_category: str, cooldown_seconds: int = 90):
    g = client.post(
        "/goals",
        json={
            "statement": "deep work",
            "priority": 4,
            "pace_target_unit": "minutes",
            "pace_target_amount": 60.0,
        },
    ).json()
    rule = client.post(
        "/distraction-rules",
        json={
            "goal_id": g["id"],
            "distractor_category": distractor_category,
            "cooldown_seconds": cooldown_seconds,
        },
    ).json()
    sess = client.post(
        "/focus/start",
        json={"intention": "x", "planned_duration_minutes": 60, "goal_id": g["id"]},
    ).json()
    return g, rule, sess


def _heartbeat(client, *, category: str, hint: str = "", active_seconds: int = 30, idle: int = 0):
    return client.post(
        "/agent/heartbeat",
        json={
            "source": "pc_agent",
            "foreground_category": category,
            "foreground_app_hint": hint,
            "active_seconds": active_seconds,
            "idle_seconds": idle,
        },
    ).json()


def test_no_rule_means_no_drift(authed_client):
    # Goal with no DistractionRule → drift never fires.
    g = authed_client.post(
        "/goals", json={"statement": "x", "pace_target_unit": "x", "pace_target_amount": 1.0}
    ).json()
    sess = authed_client.post(
        "/focus/start",
        json={"intention": "x", "planned_duration_minutes": 30, "goal_id": g["id"]},
    ).json()
    _heartbeat(authed_client, category="social_media", active_seconds=300)
    pending = authed_client.get("/interventions/pending").json()
    assert pending["interventions"] == []


def test_brief_distraction_does_not_fire(authed_client):
    _make_active_session_with_rule(
        authed_client, distractor_category="social_media", cooldown_seconds=90
    )
    _heartbeat(authed_client, category="social_media", active_seconds=30)
    pending = authed_client.get("/interventions/pending").json()
    assert pending["interventions"] == []


def test_distraction_past_cooldown_fires_tier_0(authed_client):
    _make_active_session_with_rule(
        authed_client, distractor_category="social_media", cooldown_seconds=90
    )
    # One report covering >90s in the distractor.
    resp = _heartbeat(authed_client, category="social_media", active_seconds=120)
    assert resp["drift_flagged"] is True
    pending = authed_client.get("/interventions/pending").json()
    interventions = pending["interventions"]
    assert len(interventions) == 1
    assert interventions[0]["tier"] == 0
    assert interventions[0]["reason"] == "drift:social_media"
    assert interventions[0]["session_id"] is not None


def test_returning_to_work_dismisses_live_intervention(authed_client):
    _make_active_session_with_rule(
        authed_client, distractor_category="social_media", cooldown_seconds=60
    )
    _heartbeat(authed_client, category="social_media", active_seconds=120)
    assert len(authed_client.get("/interventions/pending").json()["interventions"]) == 1
    # Now the user returns to a productive category.
    _heartbeat(authed_client, category="code_editor", active_seconds=30)
    pending = authed_client.get("/interventions/pending").json()
    assert pending["interventions"] == []


def test_tier_escalates_after_grace_period(authed_client, monkeypatch):
    """When the live tier-0 intervention's next_escalation_at is in the past
    and the user is still in the distractor, the engine fires Tier 1, then
    Tier 2 on the next pass."""
    from buddy.services import interventions as engine

    _make_active_session_with_rule(
        authed_client, distractor_category="social_media", cooldown_seconds=60
    )
    _heartbeat(authed_client, category="social_media", active_seconds=120)
    # Pretend the grace period has elapsed.
    pending = authed_client.get("/interventions/pending").json()["interventions"]
    assert pending[0]["tier"] == 0
    intervention_id = pending[0]["id"]

    # Forcibly age the next_escalation_at backwards via the DB.
    from sqlalchemy import update
    from buddy.db import get_session_factory
    from buddy.models import Intervention

    async def age():
        factory = get_session_factory()
        async with factory() as db:
            await db.execute(
                update(Intervention)
                .where(Intervention.id == intervention_id)
                .values(next_escalation_at=datetime.utcnow() - timedelta(seconds=1))
            )
            await db.commit()

    asyncio.run(age())

    # Another heartbeat keeps the user in the distractor → engine escalates.
    _heartbeat(authed_client, category="social_media", active_seconds=30)
    pending = authed_client.get("/interventions/pending").json()["interventions"]
    # Tier 0 was superseded (dismissed); only the new Tier 1 should be live.
    assert len(pending) == 1
    assert pending[0]["tier"] == 1
    new_id = pending[0]["id"]

    # Age + escalate again → Tier 2.
    async def age2():
        factory = get_session_factory()
        async with factory() as db:
            await db.execute(
                update(Intervention)
                .where(Intervention.id == new_id)
                .values(next_escalation_at=datetime.utcnow() - timedelta(seconds=1))
            )
            await db.commit()

    asyncio.run(age2())
    _heartbeat(authed_client, category="social_media", active_seconds=30)
    pending = authed_client.get("/interventions/pending").json()["interventions"]
    assert len(pending) == 1
    assert pending[0]["tier"] == 2

    # Tier 2 has no next_escalation_at — engine caps here.
    assert pending[0]["next_escalation_at"] is None


def test_floor_check_fires_for_zero_progress_goals(authed_client):
    g = authed_client.post(
        "/goals",
        json={
            "statement": "Walk daily",
            "priority": 3,
            "pace_target_unit": "minutes",
            "pace_target_amount": 30.0,
        },
    ).json()
    r = authed_client.post("/interventions/floor-check")
    assert r.status_code == 200
    fired = r.json()["interventions"]
    assert len(fired) == 1
    assert fired[0]["goal_id"] == g["id"]
    assert fired[0]["tier"] == 0
    assert fired[0]["reason"].startswith("floor_check:")


def test_floor_check_skips_goals_with_progress(authed_client):
    g = authed_client.post(
        "/goals", json={"statement": "x", "pace_target_unit": "x", "pace_target_amount": 1.0}
    ).json()
    authed_client.post(
        "/progress/log",
        json={"goal_id": g["id"], "attributed_units": 1.0, "unit_label": "x"},
    )
    fired = authed_client.post("/interventions/floor-check").json()["interventions"]
    assert fired == []


def test_intervention_action_dismiss(authed_client):
    _make_active_session_with_rule(
        authed_client, distractor_category="social_media", cooldown_seconds=60
    )
    _heartbeat(authed_client, category="social_media", active_seconds=120)
    intervention = authed_client.get("/interventions/pending").json()["interventions"][0]

    r = authed_client.post(
        f"/interventions/{intervention['id']}/action",
        json={"action": "dismissed"},
    )
    assert r.status_code == 200
    assert r.json()["dismissed_at"] is not None

    pending = authed_client.get("/interventions/pending").json()["interventions"]
    assert pending == []


def test_agent_status_when_no_session_active(authed_client):
    r = authed_client.get("/agent/status")
    assert r.status_code == 200
    body = r.json()
    assert body["active_session_id"] is None
    assert body["distractor_categories"] == []


def test_agent_status_returns_distractor_categories(authed_client):
    g, rule, sess = _make_active_session_with_rule(
        authed_client, distractor_category="video"
    )
    body = authed_client.get("/agent/status").json()
    assert body["active_session_id"] == sess["id"]
    assert body["intention"] == sess["intention"]
    assert "video" in body["distractor_categories"]
