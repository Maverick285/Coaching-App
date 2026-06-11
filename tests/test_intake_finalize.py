"""Persona intake — full happy path + LLM-failure local fallback."""

from __future__ import annotations

from tests._helpers import FakeToolResult, fake_tool_returning


def _walk_intake(client) -> str:
    """Start the intake and submit a canned answer per question kind."""
    start = client.post("/intake/start").json()
    intake_id = start["intake_id"]

    step_payload = start
    while not step_payload.get("finished"):
        q = step_payload["question"]
        if q is None:
            break
        kind = q["kind"]
        if kind == "text_short":
            ans = {"text": "Maverick"}
        elif kind == "pair_choice":
            opt = (q.get("options") or [{}])[0]
            ans = {"id": opt.get("id", "")}
        elif kind == "scale":
            ans = {"value": 3}
        elif kind == "multi_choice":
            ids = [o["id"] for o in (q.get("options") or [])][:2]
            ans = {"selected": ids}
        else:
            ans = {}
        r = client.post("/intake/turn", json={"intake_id": intake_id, "answer": ans})
        assert r.status_code == 200, r.text
        step_payload = r.json()
    return intake_id


def test_finalize_uses_local_fallback_when_llm_fails(authed_client, monkeypatch):
    """If chat_with_tool raises every retry, finalize still completes."""

    async def boom(**_):
        raise RuntimeError("anthropic blew up")

    monkeypatch.setattr("buddy.api.intake.chat_with_tool", boom)

    intake_id = _walk_intake(authed_client)
    r = authed_client.post("/intake/finalize", json={"intake_id": intake_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intake_id"] == intake_id
    assert "Persona Profile" in body["persona_md"]
    assert "Maverick" in body["memory_md"] or "About" in body["memory_md"]
    profile = authed_client.get("/profile").json()
    assert profile["onboarding_complete"] is True


def test_finalize_uses_tool_use_when_it_works(authed_client, monkeypatch):
    monkeypatch.setattr(
        "buddy.api.intake.chat_with_tool",
        fake_tool_returning(
            FakeToolResult(
                tool_name="synthesize_persona",
                tool_input={
                    "persona_md": "# Persona Profile\n\nlooks-good",
                    "memory_md": "# About Maverick\n\nlooks-good",
                    "name": "Coach",
                },
            ),
        ),
    )
    intake_id = _walk_intake(authed_client)
    r = authed_client.post("/intake/finalize", json={"intake_id": intake_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "looks-good" in body["persona_md"]
    assert "looks-good" in body["memory_md"]
