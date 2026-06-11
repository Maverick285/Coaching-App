"""Focus-session lifecycle + check-in generation."""

from __future__ import annotations

from tests._helpers import fake_chat_returning, focus_check_in_response


def test_focus_lifecycle(authed_client):
    r = authed_client.post(
        "/focus/start",
        json={"intention": "45 min on the runsheet", "planned_duration_minutes": 45},
    )
    assert r.status_code == 200
    session = r.json()
    assert session["state"] == "active"

    active = authed_client.get("/focus/active").json()
    assert active["session"]["id"] == session["id"]

    # A second start while one is active should 409.
    r = authed_client.post(
        "/focus/start",
        json={"intention": "another", "planned_duration_minutes": 30},
    )
    assert r.status_code == 409

    end = authed_client.post(
        f"/focus/{session['id']}/end",
        json={"summary": "done", "state": "completed"},
    )
    assert end.status_code == 200
    assert end.json()["state"] == "completed"

    # Active is now empty.
    active2 = authed_client.get("/focus/active").json()
    assert active2["session"] is None


def test_check_in_generation_persists_message(authed_client, monkeypatch):
    session = authed_client.post(
        "/focus/start",
        json={"intention": "deep work block", "planned_duration_minutes": 50},
    ).json()
    monkeypatch.setattr(
        "buddy.api.focus.chat",
        fake_chat_returning(focus_check_in_response("Still with you. How's it going?")),
    )

    r = authed_client.post(
        f"/focus/{session['id']}/check-in", params={"kind": "presence"}
    )
    assert r.status_code == 200
    check_in = r.json()["check_in"]
    assert check_in["kind"] == "presence"
    assert "Still with you" in check_in["message"]

    detail = authed_client.get(f"/focus/{session['id']}").json()
    assert len(detail["check_ins"]) == 1
    assert detail["check_ins"][0]["message"] == check_in["message"]


def test_check_in_invalid_kind_rejected(authed_client):
    session = authed_client.post(
        "/focus/start", json={"intention": "x", "planned_duration_minutes": 30}
    ).json()
    r = authed_client.post(
        f"/focus/{session['id']}/check-in", params={"kind": "bogus"}
    )
    assert r.status_code == 400


def test_check_in_on_inactive_session_rejected(authed_client, monkeypatch):
    session = authed_client.post(
        "/focus/start", json={"intention": "x", "planned_duration_minutes": 30}
    ).json()
    authed_client.post(
        f"/focus/{session['id']}/end", json={"summary": "", "state": "completed"}
    )

    monkeypatch.setattr(
        "buddy.api.focus.chat",
        fake_chat_returning(focus_check_in_response("…")),
    )
    r = authed_client.post(
        f"/focus/{session['id']}/check-in", params={"kind": "presence"}
    )
    assert r.status_code == 400
    assert "not active" in r.json()["detail"].lower()
