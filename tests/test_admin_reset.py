"""Hard-reset endpoint."""

from __future__ import annotations


def test_reset_wipes_goals_tasks_and_reseeds_memory(authed_client):
    # Seed: a goal + a task.
    g = authed_client.post(
        "/goals", json={"statement": "test goal", "priority": 3}
    ).json()
    authed_client.post(
        "/tasks", json={"goal_id": g["id"], "description": "do thing"}
    )
    # Confirm there's data to wipe.
    assert authed_client.get("/goals").json()["goals"], "precondition failed"

    r = authed_client.post("/admin/reset", json={"confirm": "RESET"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "goals" in body["cleared_tables"]
    assert "tasks" in body["cleared_tables"]

    # Goals + tasks gone, memory files reseeded fresh.
    assert authed_client.get("/goals").json()["goals"] == []
    files = authed_client.get("/memory/files").json()["files"]
    paths = {f["path"] for f in files}
    assert "PERSONA.md" in paths
    assert "MEMORY.md" in paths


def test_reset_requires_confirmation(authed_client):
    r = authed_client.post("/admin/reset", json={"confirm": "no"})
    assert r.status_code == 400
