"""Natural-language batch task editor."""

from __future__ import annotations

import json

from tests._helpers import fake_chat_returning


def _create_goal(client, statement: str = "Ship the spec", priority: int = 4) -> int:
    r = client.post(
        "/goals",
        json={"statement": statement, "priority": priority},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _create_task(client, goal_id: int, description: str) -> int:
    r = client.post(
        "/tasks", json={"goal_id": goal_id, "description": description}
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _ops(operations: list[dict]) -> str:
    return json.dumps({"operations": operations})


def test_batch_creates_completes_and_deletes(authed_client, monkeypatch):
    goal_id = _create_goal(authed_client)
    dishes_id = _create_task(authed_client, goal_id, "Wash the dishes")
    gym_id = _create_task(authed_client, goal_id, "Skip the gym")

    monkeypatch.setattr(
        "buddy.api.tasks_nl.chat",
        fake_chat_returning(
            _ops([
                {
                    "op": "create",
                    "goal_id": goal_id,
                    "description": "Draft the spec",
                    "estimated_duration_minutes": 90,
                },
                {"op": "complete", "task_id": dishes_id},
                {"op": "delete", "task_id": gym_id},
            ])
        ),
    )

    r = authed_client.post(
        "/tasks/batch_nl",
        json={"text": "draft the spec for 90m, dishes done, scrap the gym one"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    statuses = [(item["op"], item["status"]) for item in body["results"]]
    assert statuses == [("create", "ok"), ("complete", "ok"), ("delete", "ok")]

    listed = authed_client.get("/tasks").json()["tasks"]
    descriptions = {t["description"]: t["state"] for t in listed}
    assert descriptions.get("Draft the spec") in ("proposed", "scheduled")
    assert descriptions.get("Wash the dishes") == "done"
    assert "Skip the gym" not in descriptions  # deleted


def test_batch_unknown_task_is_reported(authed_client, monkeypatch):
    goal_id = _create_goal(authed_client)
    monkeypatch.setattr(
        "buddy.api.tasks_nl.chat",
        fake_chat_returning(_ops([{"op": "complete", "task_id": 9999}])),
    )

    r = authed_client.post(
        "/tasks/batch_nl", json={"text": "mark the laundry done"}
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert results[0]["status"] == "error"
    assert "not found" in results[0]["detail"]


def test_batch_invalid_json_is_502(authed_client, monkeypatch):
    monkeypatch.setattr(
        "buddy.api.tasks_nl.chat",
        fake_chat_returning("not json"),
    )
    r = authed_client.post(
        "/tasks/batch_nl", json={"text": "do something"}
    )
    assert r.status_code == 502
