"""End-to-end smoke test for /converse.

The previous spec-gap shipout had zero coverage on this endpoint, which
let two 500-class bugs slip into production:
  1. OpenAI 401 on embeddings cascading into a 500 instead of falling
     back to BM25-only.
  2. (Future) any other unhandled exception on the assemble→prompt→chat
     pipeline.

This test hits the real path with the LLM mocked so any new regression
that breaks the wire-up surfaces locally before the user sees a 500.
"""

from __future__ import annotations

from tests._helpers import fake_chat_returning


def test_converse_happy_path(authed_client, monkeypatch):
    monkeypatch.setattr(
        "buddy.api.converse.chat",
        fake_chat_returning("Hey. What's on your mind?"),
    )
    r = authed_client.post("/converse", json={"message": "hi"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "session_id" in body
    assert body["response"].startswith("Hey")


def test_converse_falls_back_when_embedding_fails(authed_client, monkeypatch):
    """A bad/expired OpenAI key shouldn't 500 the chat path. The
    embedding call is best-effort; on failure we fall back to BM25."""

    async def bad_embed(_texts):
        raise RuntimeError("openai 401: invalid_api_key")

    monkeypatch.setattr("buddy.memory.search.embed", bad_embed)
    monkeypatch.setattr(
        "buddy.api.converse.chat",
        fake_chat_returning("Got it. Keyword search only this turn."),
    )
    r = authed_client.post("/converse", json={"message": "what did i do yesterday?"})
    assert r.status_code == 200, r.text
    assert r.json()["response"].startswith("Got it")


def test_converse_anthropic_failure_returns_502(authed_client, monkeypatch):
    """When Anthropic itself fails, surface a 502 with the real error
    text — no opaque 'something went wrong'."""

    async def boom(**_):
        raise RuntimeError("anthropic api: overloaded_error")

    monkeypatch.setattr("buddy.api.converse.chat", boom)
    r = authed_client.post("/converse", json={"message": "hi"})
    assert r.status_code == 502
    assert "overloaded_error" in r.text
