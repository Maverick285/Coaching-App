"""2-4 active top-level goal cap (master spec §20.1)."""

from __future__ import annotations


def test_create_blocked_at_active_limit(authed_client):
    for i in range(4):
        r = authed_client.post(
            "/goals", json={"statement": f"goal {i}", "priority": 3}
        )
        assert r.status_code == 200, r.text

    blocked = authed_client.post(
        "/goals", json={"statement": "5th one", "priority": 3}
    )
    assert blocked.status_code == 409
    body = blocked.json()
    assert body["detail"]["code"] == "active_goal_limit"
    assert body["detail"]["limit"] == 4


def test_subgoals_dont_count_against_limit(authed_client):
    # Create 4 active top-level goals at the cap.
    parent_ids: list[int] = []
    for i in range(4):
        r = authed_client.post("/goals", json={"statement": f"g{i}"})
        parent_ids.append(r.json()["id"])

    # Sub-goal of g0 should be allowed even though we're at the cap.
    r = authed_client.post(
        "/goals",
        json={"statement": "milestone of g0", "parent_goal_id": parent_ids[0]},
    )
    assert r.status_code == 200, r.text


def test_pausing_a_goal_frees_a_slot(authed_client):
    ids = []
    for i in range(4):
        ids.append(authed_client.post("/goals", json={"statement": f"g{i}"}).json()["id"])

    # Pause goal 0.
    paused = authed_client.patch(f"/goals/{ids[0]}", json={"state": "paused"})
    assert paused.status_code == 200

    # Now create succeeds again.
    r = authed_client.post("/goals", json={"statement": "fresh"})
    assert r.status_code == 200


def test_resuming_when_at_cap_is_blocked(authed_client):
    paused_id = authed_client.post(
        "/goals", json={"statement": "paused-from-the-start"}
    ).json()["id"]
    authed_client.patch(f"/goals/{paused_id}", json={"state": "paused"})
    # Fill up the active cap.
    for i in range(4):
        authed_client.post("/goals", json={"statement": f"active-{i}"})
    # Trying to flip the paused one back to active should 409.
    r = authed_client.patch(f"/goals/{paused_id}", json={"state": "active"})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "active_goal_limit"
