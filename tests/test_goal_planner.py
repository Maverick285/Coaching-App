"""Wish → structured plan endpoint."""

from __future__ import annotations

from datetime import date, timedelta

from tests._helpers import FakeToolResult, fake_tool_returning


def _plan_payload(**overrides):
    base = {
        "statement": "Drop to 15% body fat by August",
        "rationale": "Steady deficit + 3 strength sessions a week works.",
        "user_facing_summary": "We'll aim for 0.5 lb fat lost per week. The minimum that still counts is a 10-min walk.",
        "pace_target_unit": "lbs lost",
        "pace_target_amount": 0.5,
        "pace_target_description": "0.5 lb fat lost per week.",
        "mvp_threshold": "10-minute walk",
        "intervention_ceiling": 2,
        "approach": "hybrid",
        "priority": 4,
        "milestones": [
            {
                "statement": "Lose first 5 lbs",
                "deadline": None,
                "pace_target_unit": "lbs lost",
                "pace_target_amount": 0.5,
                "mvp_threshold": "weigh in",
            }
        ],
        "first_week_tasks": [
            {
                "description": "Set up a kitchen scale and log dinner tonight",
                "estimated_duration_minutes": 5,
                "first_60_seconds": "Open the cabinet under the sink",
                "scheduled_at": None,
            },
            {
                "description": "Lift A — full body, 45 minutes",
                "estimated_duration_minutes": 45,
                "first_60_seconds": "Put on shoes",
                "scheduled_at": None,
            },
        ],
        "implementation_intentions": [
            {
                "cue_type": "obstacle",
                "cue_text": "I'm hungry after 9 PM",
                "response_text": "Drink a glass of water and brush teeth",
            },
            {
                "cue_type": "time_place",
                "cue_text": "Monday 6 PM gym",
                "response_text": "Lift A workout",
            },
        ],
        "obstacles": ["late-night snacking", "weekend skipped lifts"],
        "outcome_vision": "Suit fits at the conference. You feel strong.",
    }
    base.update(overrides)
    return base


def _planner_mock(payload: dict) -> object:
    return fake_tool_returning(
        FakeToolResult(tool_name="propose_goal_plan", tool_input=payload),
    )


def test_plan_returns_structured_plan(authed_client, monkeypatch):
    monkeypatch.setattr(
        "buddy.api.goal_planner.chat_with_tool", _planner_mock(_plan_payload())
    )
    deadline = (date.today() + timedelta(days=120)).isoformat()
    r = authed_client.post(
        "/goals/plan",
        json={"wish": "Get to 15% body fat", "deadline": deadline},
    )
    assert r.status_code == 200, r.text
    body = r.json()["plan"]
    assert body["pace_target_unit"] == "lbs lost"
    assert len(body["first_week_tasks"]) == 2
    assert body["implementation_intentions"][0]["cue_type"] == "obstacle"


def test_plan_apply_creates_goal_milestones_tasks_intentions(authed_client, monkeypatch):
    monkeypatch.setattr(
        "buddy.api.goal_planner.chat_with_tool", _planner_mock(_plan_payload())
    )
    deadline = (date.today() + timedelta(days=120)).isoformat()
    plan = authed_client.post(
        "/goals/plan",
        json={"wish": "Get to 15% body fat", "deadline": deadline},
    ).json()["plan"]

    r = authed_client.post("/goals/plan/apply", json={"plan": plan})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["goal_id"] > 0
    assert len(body["milestone_ids"]) == 1
    assert len(body["task_ids"]) == 2
    assert len(body["intention_ids"]) == 2

    detail = authed_client.get(f"/goals/{body['goal_id']}").json()["goal"]
    assert detail["pace_target_unit"] == "lbs lost"
    assert detail["mvp_threshold"] == "10-minute walk"
    assert detail["state"] == "active"
    listed = authed_client.get("/goals").json()["goals"]
    sub = next(g for g in listed if g["id"] == body["milestone_ids"][0])
    assert sub["parent_goal_id"] == body["goal_id"]


def test_plan_rejects_past_deadline(authed_client, monkeypatch):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    r = authed_client.post(
        "/goals/plan",
        json={"wish": "Anything", "deadline": yesterday},
    )
    assert r.status_code == 400


def test_plan_retries_on_transient_tool_failure(authed_client, monkeypatch):
    """First attempt raises, second succeeds — endpoint returns 200."""
    calls = {"i": 0}
    payload = _plan_payload()

    async def flaky(**kwargs):
        calls["i"] += 1
        if calls["i"] == 1:
            raise RuntimeError("transient")
        return FakeToolResult(tool_name="propose_goal_plan", tool_input=payload)

    monkeypatch.setattr("buddy.api.goal_planner.chat_with_tool", flaky)
    r = authed_client.post("/goals/plan", json={"wish": "Read more"})
    assert r.status_code == 200
    assert calls["i"] == 2
