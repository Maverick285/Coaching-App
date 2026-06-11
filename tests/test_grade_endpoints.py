"""Day-grade computation + finalization, streak shape."""

from __future__ import annotations


def test_grade_today_with_no_active_goals_is_zero(authed_client):
    r = authed_client.get("/grade/today")
    assert r.status_code == 200
    body = r.json()
    assert body["system_score"] == 0.0
    assert body["per_goal"] == []
    # is_zero_day requires at least one active goal that scored 0;
    # with no active goals, it's defined as False.
    assert body["is_zero_day"] is False


def test_grade_today_reflects_progress_log(authed_client):
    g = authed_client.post(
        "/goals",
        json={
            "statement": "X",
            "priority": 3,
            "pace_target_unit": "pages",
            "pace_target_amount": 20.0,
        },
    ).json()
    authed_client.post(
        "/progress/log",
        json={
            "goal_id": g["id"],
            "attributed_units": 10.0,
            "unit_label": "pages",
            "raw_text": "10 pages",
        },
    )
    grade = authed_client.get("/grade/today").json()
    assert grade["system_score"] == 0.5
    assert grade["per_goal"][0]["progress_today"] == 10.0


def test_grade_finalize_accept_system(authed_client):
    g = authed_client.post(
        "/goals",
        json={
            "statement": "Y",
            "priority": 5,
            "pace_target_unit": "x",
            "pace_target_amount": 1.0,
        },
    ).json()
    authed_client.post(
        "/progress/log",
        json={"goal_id": g["id"], "attributed_units": 1.0, "unit_label": "x"},
    )
    today = authed_client.get("/grade/today").json()["grade_date"]

    r = authed_client.post(
        f"/grade/{today}/finalize",
        json={"accept_system_score": True, "user_notes": "good day"},
    )
    assert r.status_code == 200
    final = r.json()
    assert final["finalized"] is True
    assert final["user_score"] == final["system_score"]
    assert final["user_notes"] == "good day"


def test_grade_finalize_user_override(authed_client):
    g = authed_client.post(
        "/goals",
        json={
            "statement": "Z",
            "pace_target_unit": "x",
            "pace_target_amount": 10.0,
        },
    ).json()
    authed_client.post(
        "/progress/log",
        json={"goal_id": g["id"], "attributed_units": 3.0, "unit_label": "x"},
    )
    today = authed_client.get("/grade/today").json()["grade_date"]

    r = authed_client.post(
        f"/grade/{today}/finalize",
        json={"accept_system_score": False, "user_score": 0.9, "user_notes": "off-record effort"},
    )
    final = r.json()
    assert final["user_score"] == 0.9
    assert final["finalized"] is True


def test_streak_with_no_history(authed_client):
    r = authed_client.get("/streak")
    assert r.status_code == 200
    body = r.json()
    # Without any DayGrade rows, every day is a pause; current streak length is 0.
    assert body["current_streak_length"] == 0
    assert len(body["history"]) == 30
    assert all(d["is_pause"] for d in body["history"])
