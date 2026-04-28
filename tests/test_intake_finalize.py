"""Persona intake — full happy path + LLM-failure local fallback."""

from __future__ import annotations

import json

from tests._helpers import fake_chat_returning


def _walk_intake(client) -> str:
    """Start the intake and submit a canned answer per question kind.
    Returns the intake_id so the test can finalize it.
    """
    start = client.post("/intake/start").json()
    intake_id = start["intake_id"]
    total = start["total_steps"]

    # Answer each step until finished, supplying the right shape per kind.
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
    """If the LLM raises every retry, finalize still completes — the user
    gets a deterministically-rendered PERSONA.md/MEMORY.md and the app
    proceeds to onboarded state."""

    async def boom(**_):
        raise RuntimeError("anthropic blew up")

    monkeypatch.setattr("buddy.api.intake.chat", boom)

    intake_id = _walk_intake(authed_client)
    r = authed_client.post("/intake/finalize", json={"intake_id": intake_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intake_id"] == intake_id
    assert "Persona Profile" in body["persona_md"]
    assert "Maverick" in body["memory_md"] or "About" in body["memory_md"]
    # No LLM means no api_usage row; that's fine. Profile should now be
    # marked onboarded.
    profile = authed_client.get("/profile").json()
    assert profile["onboarding_complete"] is True


def test_finalize_uses_llm_synthesis_when_it_works(authed_client, monkeypatch):
    payload = {
        "persona_md": "# Persona Profile\n\nlooks-good",
        "memory_md": "# About Maverick\n\nlooks-good",
        "name": "Coach",
    }
    monkeypatch.setattr(
        "buddy.api.intake.chat",
        fake_chat_returning(json.dumps(payload)),
    )
    intake_id = _walk_intake(authed_client)
    r = authed_client.post("/intake/finalize", json={"intake_id": intake_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "looks-good" in body["persona_md"]
    assert "looks-good" in body["memory_md"]
