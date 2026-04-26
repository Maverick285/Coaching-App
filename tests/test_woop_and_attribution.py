"""WOOP synthesis + free-form progress attribution."""

from __future__ import annotations

from tests._helpers import (
    fake_chat_returning,
    progress_attribution_response,
    woop_response,
)


def test_woop_returns_structured_plan(authed_client, monkeypatch):
    monkeypatch.setattr(
        "buddy.api.goals.chat",
        fake_chat_returning(
            woop_response(
                wish="Get to 12% body fat by August",
                outcome="Vivid scene of fitting into the suit.",
                obstacles=["Late nights derail diet."],
                plan=["If it's after 9 PM, then no second helping."],
                pace_unit="lbs/week",
                pace_amount=0.4,
                pace_description="0.4 lb fat loss per week.",
            )
        ),
    )
    r = authed_client.post(
        "/goals/woop",
        json={"wish": "Get to 12% body fat by August"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["wish"] == "Get to 12% body fat by August"
    assert body["obstacles"] == ["Late nights derail diet."]
    assert body["plan"][0].startswith("If")
    assert body["suggested_pace_amount"] == 0.4
    assert body["suggested_pace_unit"] == "lbs/week"


def test_woop_invalid_json_is_502(authed_client, monkeypatch):
    monkeypatch.setattr(
        "buddy.api.goals.chat",
        fake_chat_returning("definitely not json"),
    )
    r = authed_client.post("/goals/woop", json={"wish": "anything"})
    assert r.status_code == 502


def test_progress_freeform_attributes_to_active_goals(authed_client, monkeypatch):
    g = authed_client.post(
        "/goals",
        json={
            "statement": "Read 24 books this year",
            "priority": 4,
            "pace_target_unit": "pages",
            "pace_target_amount": 18.0,
        },
    ).json()
    monkeypatch.setattr(
        "buddy.api.progress.chat",
        fake_chat_returning(
            progress_attribution_response(
                [
                    {
                        "goal_id": g["id"],
                        "units": 30,
                        "unit_label": "pages",
                        "confidence": 0.95,
                        "rationale": "user said '30 pages'",
                    }
                ]
            )
        ),
    )

    r = authed_client.post(
        "/progress/freeform", json={"text": "read 30 pages this morning"}
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["logged"]) == 1
    assert body["logged"][0]["attributed_units"] == 30
    assert body["logged"][0]["goal_id"] == g["id"]


def test_progress_freeform_no_active_goals(authed_client, monkeypatch):
    # No goals created. Should return empty attributions.
    r = authed_client.post(
        "/progress/freeform", json={"text": "did something"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["attributions"] == []
    assert body["unattributed_text"] == "did something"


def test_progress_freeform_skips_zero_units(authed_client, monkeypatch):
    g = authed_client.post(
        "/goals", json={"statement": "X", "pace_target_unit": "x", "pace_target_amount": 1.0}
    ).json()
    monkeypatch.setattr(
        "buddy.api.progress.chat",
        fake_chat_returning(
            progress_attribution_response(
                [
                    {
                        "goal_id": g["id"],
                        "units": 0,
                        "unit_label": "x",
                        "confidence": 0.4,
                        "rationale": "?",
                    }
                ]
            )
        ),
    )
    r = authed_client.post(
        "/progress/freeform", json={"text": "ambiguous"}
    )
    assert r.json()["logged"] == []
