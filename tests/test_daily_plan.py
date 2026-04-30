"""Daily-plan generation + per-item action paths."""

from __future__ import annotations

from tests._helpers import FakeToolResult, fake_tool_returning


def _mock_generate(payload: dict) -> object:
    return fake_tool_returning(
        FakeToolResult(tool_name="generate_daily_plan", tool_input=payload),
    )


def test_today_with_no_goals_returns_empty_plan(authed_client):
    r = authed_client.get("/daily-plan/today")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"] == []
    # Same date, second call returns same plan id (idempotent).
    r2 = authed_client.get("/daily-plan/today")
    assert r2.json()["id"] == body["id"]


def test_today_generates_items_from_active_goals(authed_client, monkeypatch):
    g = authed_client.post(
        "/goals",
        json={
            "statement": "Read 24 books this year",
            "priority": 4,
            "pace_target_unit": "pages",
            "pace_target_amount": 18.0,
            "mvp_threshold": "5 pages",
        },
    ).json()

    monkeypatch.setattr(
        "buddy.services.daily_plan.chat_with_tool",
        _mock_generate(
            {
                "rationale": "Light reading day; stay on the 18-page pace.",
                "items": [
                    {
                        "goal_id": g["id"],
                        "task_text": "Read 18 pages of the current book",
                        "tier": "must",
                        "est_minutes": 30,
                        "rationale": "Pace target.",
                    },
                    {
                        "goal_id": g["id"],
                        "task_text": "Add highlights to the journal",
                        "tier": "could",
                        "est_minutes": 10,
                        "rationale": "Optional reflection.",
                    },
                ],
            }
        ),
    )

    r = authed_client.get("/daily-plan/today")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rationale"].startswith("Light reading")
    assert len(body["items"]) == 2
    must = [i for i in body["items"] if i["tier"] == "must"]
    assert len(must) == 1
    assert must[0]["task_text"].startswith("Read 18")
    assert must[0]["est_minutes"] == 30


def test_items_with_unknown_goal_id_are_dropped(authed_client, monkeypatch):
    g = authed_client.post("/goals", json={"statement": "g"}).json()
    monkeypatch.setattr(
        "buddy.services.daily_plan.chat_with_tool",
        _mock_generate(
            {
                "rationale": "",
                "items": [
                    {
                        "goal_id": g["id"],
                        "task_text": "valid",
                        "tier": "must",
                        "est_minutes": 30,
                    },
                    {
                        "goal_id": 99999,
                        "task_text": "invalid",
                        "tier": "must",
                        "est_minutes": 30,
                    },
                ],
            }
        ),
    )
    r = authed_client.get("/daily-plan/today").json()
    assert len(r["items"]) == 1
    assert r["items"][0]["task_text"] == "valid"


def test_action_done(authed_client, monkeypatch):
    g = authed_client.post("/goals", json={"statement": "g"}).json()
    monkeypatch.setattr(
        "buddy.services.daily_plan.chat_with_tool",
        _mock_generate(
            {
                "rationale": "",
                "items": [
                    {"goal_id": g["id"], "task_text": "t", "tier": "must", "est_minutes": 30}
                ],
            }
        ),
    )
    item_id = authed_client.get("/daily-plan/today").json()["items"][0]["id"]
    r = authed_client.post(
        f"/daily-plan/items/{item_id}/action",
        json={"action": "done"},
    )
    assert r.status_code == 200
    assert r.json()["state"] == "done"


def test_action_defer_with_freetext_reason_parses_defer_until(authed_client, monkeypatch):
    g = authed_client.post("/goals", json={"statement": "g"}).json()
    # First call generates the plan; second is the deferral parse.
    from buddy.llm.client import ChatWithToolsResult  # noqa: F401  (not used here)
    from buddy.llm.client import ToolCallResult

    calls: list[str] = []

    async def mock_tool_router(**kwargs):
        tool_name = kwargs["tool"]["name"]
        calls.append(tool_name)
        if tool_name == "generate_daily_plan":
            return ToolCallResult(
                tool_name="generate_daily_plan",
                tool_input={
                    "rationale": "",
                    "items": [
                        {"goal_id": g["id"], "task_text": "t", "tier": "must", "est_minutes": 30}
                    ],
                },
                text="",
                model="fake",
                tokens_in=100,
                tokens_out=50,
                cost_usd=0.001,
                raw=None,
            )
        if tool_name == "parse_deferral_reason":
            return ToolCallResult(
                tool_name="parse_deferral_reason",
                tool_input={
                    "defer_until_iso": "2026-05-01",
                    "context_note": "User in OKC tomorrow; books available there.",
                },
                text="",
                model="fake",
                tokens_in=50,
                tokens_out=25,
                cost_usd=0.0005,
                raw=None,
            )
        raise AssertionError(f"unexpected tool {tool_name}")

    monkeypatch.setattr("buddy.services.daily_plan.chat_with_tool", mock_tool_router)

    item_id = authed_client.get("/daily-plan/today").json()["items"][0]["id"]
    r = authed_client.post(
        f"/daily-plan/items/{item_id}/action",
        json={
            "action": "defer",
            "reason": "I'll do that tomorrow while I'm in OKC",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "deferred"
    assert body["defer_reason"] == "I'll do that tomorrow while I'm in OKC"
    assert body["defer_until"] == "2026-05-01"
    assert "OKC" in body["defer_context"]
    assert "parse_deferral_reason" in calls
