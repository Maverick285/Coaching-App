"""Phase 5: blocked-app rules, override request lifecycle, engine
ceiling-respect, override-active suppression."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta


def _make_active_session(client, *, ceiling: int = 4):
    g = client.post(
        "/goals",
        json={
            "statement": "deep work",
            "priority": 4,
            "pace_target_unit": "minutes",
            "pace_target_amount": 60.0,
            "intervention_ceiling": ceiling,
        },
    ).json()
    sess = client.post(
        "/focus/start",
        json={"intention": "x", "planned_duration_minutes": 60, "goal_id": g["id"]},
    ).json()
    return g, sess


# ---- Blocked-app rules CRUD --------------------------------------------


def test_blocked_app_crud(authed_client):
    g, _ = _make_active_session(authed_client)
    r = authed_client.post(
        "/blocked-apps",
        json={"goal_id": g["id"], "package_name": "com.twitter.android", "block_tier": 4},
    )
    assert r.status_code == 200
    rule = r.json()
    assert rule["block_tier"] == 4

    listed = authed_client.get("/blocked-apps", params={"goal_id": g["id"]}).json()
    assert len(listed["rules"]) == 1

    deleted = authed_client.delete(f"/blocked-apps/{rule['id']}")
    assert deleted.status_code == 200

    listed2 = authed_client.get("/blocked-apps", params={"goal_id": g["id"]}).json()
    assert listed2["rules"] == []


def test_blocked_app_active_returns_session_blocks(authed_client):
    g, sess = _make_active_session(authed_client)
    authed_client.post(
        "/blocked-apps",
        json={"goal_id": g["id"], "package_name": "com.x.android", "block_tier": 3},
    )
    body = authed_client.get("/blocked-apps/active").json()
    assert body["override_window_open"] is False
    assert len(body["blocks"]) == 1
    assert body["blocks"][0]["package_name"] == "com.x.android"
    assert body["blocks"][0]["block_tier"] == 3
    assert body["blocks"][0]["session_id"] == sess["id"]


def test_active_blocks_empty_when_no_session(authed_client):
    g = authed_client.post(
        "/goals", json={"statement": "x", "pace_target_unit": "x", "pace_target_amount": 1.0}
    ).json()
    authed_client.post(
        "/blocked-apps",
        json={"goal_id": g["id"], "package_name": "com.x.android", "block_tier": 3},
    )
    body = authed_client.get("/blocked-apps/active").json()
    assert body["blocks"] == []


# ---- Override lifecycle ------------------------------------------------


def test_override_request_in_dev_mode_echoes_code(authed_client):
    g, sess = _make_active_session(authed_client)
    r = authed_client.post(
        "/overrides",
        json={
            "package_name": "com.twitter.android",
            "reason": "expecting an important DM",
            "session_id": sess["id"],
            "goal_id": g["id"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["sms_status"] == "log_only"
    assert body["code_dev_echo"] is not None
    assert len(body["code_dev_echo"]) == 6


def test_override_redeem_with_correct_code_opens_window(authed_client):
    g, sess = _make_active_session(authed_client)
    req = authed_client.post(
        "/overrides",
        json={
            "package_name": "com.twitter.android",
            "reason": "x",
            "session_id": sess["id"],
            "goal_id": g["id"],
            "active_minutes": 5,
        },
    ).json()
    code = req["code_dev_echo"]
    r = authed_client.post(f"/overrides/{req['id']}/redeem", json={"code": code})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["request"]["status"] == "approved"
    assert body["request"]["expires_at"] is not None


def test_override_redeem_wrong_code_fails(authed_client):
    g, sess = _make_active_session(authed_client)
    req = authed_client.post(
        "/overrides",
        json={"package_name": "x", "reason": "x", "session_id": sess["id"], "goal_id": g["id"]},
    ).json()
    r = authed_client.post(f"/overrides/{req['id']}/redeem", json={"code": "000000"})
    body = r.json()
    assert body["success"] is False
    assert "did not match" in body["message"].lower()
    assert body["request"]["status"] == "pending"


def test_active_override_window_suppresses_blocks(authed_client):
    g, sess = _make_active_session(authed_client)
    authed_client.post(
        "/blocked-apps",
        json={"goal_id": g["id"], "package_name": "com.twitter.android", "block_tier": 4},
    )
    req = authed_client.post(
        "/overrides",
        json={
            "package_name": "com.twitter.android",
            "reason": "x",
            "session_id": sess["id"],
            "goal_id": g["id"],
        },
    ).json()
    authed_client.post(f"/overrides/{req['id']}/redeem", json={"code": req["code_dev_echo"]})

    body = authed_client.get("/blocked-apps/active").json()
    assert body["override_window_open"] is True
    assert body["blocks"] == []


# ---- Engine respects per-goal intervention_ceiling --------------------


def _heartbeat(client, category="social_media", active_seconds=120):
    return client.post(
        "/agent/heartbeat",
        json={
            "source": "pc_agent",
            "foreground_category": category,
            "active_seconds": active_seconds,
        },
    ).json()


def _force_age_intervention(intervention_id):
    """Backdate next_escalation_at so the next engine tick escalates."""
    from sqlalchemy import update
    from buddy.db import get_session_factory
    from buddy.models import Intervention

    async def _impl():
        factory = get_session_factory()
        async with factory() as db:
            await db.execute(
                update(Intervention)
                .where(Intervention.id == intervention_id)
                .values(next_escalation_at=datetime.utcnow() - timedelta(seconds=1))
            )
            await db.commit()

    asyncio.run(_impl())


def test_engine_respects_ceiling_2(authed_client):
    """Goal with intervention_ceiling=2 should NEVER escalate to Tier 3
    even if drift continues."""
    g, _ = _make_active_session(authed_client, ceiling=2)
    authed_client.post(
        "/distraction-rules",
        json={"goal_id": g["id"], "distractor_category": "social_media", "cooldown_seconds": 60},
    )
    _heartbeat(authed_client, "social_media", active_seconds=120)
    pending = authed_client.get("/interventions/pending").json()["interventions"]
    assert pending[0]["tier"] == 0

    # Escalate to 1, 2 — but Tier 3 should never appear.
    for _ in range(3):
        _force_age_intervention(
            authed_client.get("/interventions/pending").json()["interventions"][0]["id"]
        )
        _heartbeat(authed_client, "social_media", active_seconds=30)

    tiers = [p["tier"] for p in authed_client.get("/interventions/pending").json()["interventions"]]
    assert max(tiers) == 2


def test_engine_can_reach_tier_3_when_ceiling_is_4(authed_client):
    g, _ = _make_active_session(authed_client, ceiling=4)
    authed_client.post(
        "/distraction-rules",
        json={"goal_id": g["id"], "distractor_category": "social_media", "cooldown_seconds": 60},
    )
    _heartbeat(authed_client, "social_media", active_seconds=120)
    # Escalate Tier 0 → 1 → 2 → 3.
    for _ in range(3):
        live = authed_client.get("/interventions/pending").json()["interventions"][0]
        _force_age_intervention(live["id"])
        _heartbeat(authed_client, "social_media", active_seconds=30)
    pending = authed_client.get("/interventions/pending").json()["interventions"]
    assert pending[0]["tier"] >= 3


def test_active_override_suppresses_engine_tick(authed_client):
    """An open override window pauses drift detection entirely."""
    g, sess = _make_active_session(authed_client)
    authed_client.post(
        "/distraction-rules",
        json={"goal_id": g["id"], "distractor_category": "social_media", "cooldown_seconds": 60},
    )
    req = authed_client.post(
        "/overrides",
        json={"package_name": "x", "reason": "x", "session_id": sess["id"], "goal_id": g["id"]},
    ).json()
    authed_client.post(f"/overrides/{req['id']}/redeem", json={"code": req["code_dev_echo"]})

    _heartbeat(authed_client, "social_media", active_seconds=300)
    pending = authed_client.get("/interventions/pending").json()["interventions"]
    assert pending == []
