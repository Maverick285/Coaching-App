"""Capture-anywhere pipeline: classify → confirm → dispatch."""

from __future__ import annotations

from tests._helpers import FakeToolResult, fake_tool_returning


def _capture_mock(actions: list, fallback: str = "") -> object:
    return fake_tool_returning(
        FakeToolResult(
            tool_name="classify_capture",
            tool_input={"actions": actions, "fallback_message": fallback},
        ),
    )


def _make_goal(client, **overrides):
    payload = {
        "statement": "Read 24 books this year",
        "priority": 4,
        "pace_target_unit": "pages",
        "pace_target_amount": 18.0,
    }
    payload.update(overrides)
    r = client.post("/goals", json=payload)
    r.raise_for_status()
    return r.json()


def test_capture_classify_returns_actions(authed_client, monkeypatch):
    goal = _make_goal(authed_client)
    monkeypatch.setattr(
        "buddy.api.capture.chat_with_tool",
        _capture_mock(
            [
                {
                    "kind": "log_progress",
                    "summary": "Log 18 pages on Reading.",
                    "payload": {
                        "goal_id": goal["id"],
                        "attributed_units": 18.0,
                        "unit_label": "pages",
                        "raw_text": "read 18 pages",
                    },
                    "confidence": 0.9,
                }
            ]
        ),
    )

    r = authed_client.post(
        "/capture", json={"text": "read 18 pages today", "source": "manual"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["raw_text"] == "read 18 pages today"
    assert len(body["actions"]) == 1
    assert body["actions"][0]["kind"] == "log_progress"
    assert body["capture_id"] > 0


def test_capture_confirm_dispatches_log_progress(authed_client, monkeypatch):
    goal = _make_goal(authed_client)
    monkeypatch.setattr(
        "buddy.api.capture.chat_with_tool",
        _capture_mock(
            [
                {
                    "kind": "log_progress",
                    "summary": "Log 18 pages on Reading.",
                    "payload": {
                        "goal_id": goal["id"],
                        "attributed_units": 18.0,
                        "unit_label": "pages",
                        "raw_text": "read 18 pages",
                    },
                    "confidence": 0.9,
                }
            ]
        ),
    )

    classify = authed_client.post(
        "/capture", json={"text": "read 18 pages today"}
    ).json()
    confirm = authed_client.post(
        "/capture/confirm",
        json={"capture_id": classify["capture_id"], "actions": classify["actions"]},
    )
    assert confirm.status_code == 200
    body = confirm.json()
    assert len(body["results"]) == 1
    res = body["results"][0]
    assert res["success"] is True
    assert res["kind"] == "log_progress"
    assert res["created_id"] is not None

    # Grade should reflect the logged progress.
    grade = authed_client.get("/grade/today").json()
    assert grade["system_score"] >= 1.0


def test_capture_dispatches_journal_note(authed_client, monkeypatch):
    monkeypatch.setattr(
        "buddy.api.capture.chat_with_tool",
        _capture_mock(
            [
                {
                    "kind": "journal_note",
                    "summary": "Add a journal note.",
                    "payload": {
                        "content": "felt clear-headed after the workout",
                        "mood": "clear",
                    },
                    "confidence": 0.95,
                }
            ]
        ),
    )
    classify = authed_client.post(
        "/capture", json={"text": "note: felt clear-headed after the workout"}
    ).json()
    confirm = authed_client.post(
        "/capture/confirm",
        json={"capture_id": classify["capture_id"], "actions": classify["actions"]},
    )
    assert confirm.json()["results"][0]["success"] is True

    from datetime import date

    today = date.today().isoformat()
    j = authed_client.get(f"/journal/{today}").json()
    assert "clear-headed" in j["content"]


def test_capture_partial_failure_does_not_block_other_actions(
    authed_client, monkeypatch
):
    goal = _make_goal(authed_client)
    monkeypatch.setattr(
        "buddy.api.capture.chat_with_tool",
        _capture_mock(
            [
                {
                    "kind": "log_progress",
                    "summary": "Log 18 pages.",
                    "payload": {
                        "goal_id": goal["id"],
                        "attributed_units": 18.0,
                        "unit_label": "pages",
                        "raw_text": "18 pages",
                    },
                    "confidence": 0.9,
                },
                {
                    "kind": "log_progress",
                    "summary": "Log to non-existent goal.",
                    "payload": {
                        "goal_id": 99999,
                        "attributed_units": 5.0,
                        "unit_label": "x",
                        "raw_text": "stale ref",
                    },
                    "confidence": 0.3,
                },
            ]
        ),
    )

    classify = authed_client.post("/capture", json={"text": "..."}).json()
    confirm = authed_client.post(
        "/capture/confirm",
        json={"capture_id": classify["capture_id"], "actions": classify["actions"]},
    )
    results = confirm.json()["results"]
    assert results[0]["success"] is True
    assert results[1]["success"] is False
    assert "99999" in results[1]["detail"] or "not found" in results[1]["detail"].lower()


def test_capture_empty_actions_with_fallback(authed_client, monkeypatch):
    monkeypatch.setattr(
        "buddy.api.capture.chat_with_tool",
        _capture_mock([], fallback="Couldn't tell what to do."),
    )
    r = authed_client.post("/capture", json={"text": "garbled words"}).json()
    assert r["actions"] == []
    assert r["fallback_message"] == "Couldn't tell what to do."
