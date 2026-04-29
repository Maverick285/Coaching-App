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

def _fake_text_response(text: str):
    """Build a fake chat_with_optional_tools that emits only prose."""
    from buddy.llm.client import ChatWithToolsResult

    async def _impl(**kwargs):
        return ChatWithToolsResult(
            text=text,
            tool_calls=[],
            model="fake",
            tokens_in=100,
            tokens_out=50,
            cost_usd=0.001,
            raw=None,
        )

    return _impl


def test_converse_happy_path(authed_client, monkeypatch):
    monkeypatch.setattr(
        "buddy.api.converse.chat_with_optional_tools",
        _fake_text_response("Hey. What's on your mind?"),
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
        "buddy.api.converse.chat_with_optional_tools",
        _fake_text_response("Got it. Keyword search only this turn."),
    )
    r = authed_client.post("/converse", json={"message": "what did i do yesterday?"})
    assert r.status_code == 200, r.text
    assert r.json()["response"].startswith("Got it")


def test_converse_surfaces_propose_goal_as_proposed_action(authed_client, monkeypatch):
    """The persona's propose_goal tool call should round-trip into
    ConverseResponse.proposed_actions so the chat client can render
    the inline confirmation card. Master spec §44.5 high-stakes path."""
    from buddy.llm.client import ChatWithToolsResult, OfferedToolCall

    async def fake_chat_with_tools(**kwargs):
        return ChatWithToolsResult(
            text="Got it. Want me to set this up?",
            tool_calls=[
                OfferedToolCall(
                    name="propose_goal",
                    input={
                        "statement": "Read 24 books this year",
                        "rationale": "You said this matters to you.",
                        "priority": 4,
                        "pace_target_amount": 18,
                        "pace_target_unit": "pages",
                        "mvp_threshold": "5 pages",
                    },
                )
            ],
            model="fake",
            tokens_in=100,
            tokens_out=50,
            cost_usd=0.001,
            raw=None,
        )

    monkeypatch.setattr("buddy.api.converse.chat_with_optional_tools", fake_chat_with_tools)
    r = authed_client.post(
        "/converse",
        json={"message": "I want to read 24 books this year"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    actions = body["proposed_actions"]
    assert len(actions) == 1
    assert actions[0]["kind"] == "propose_goal"
    assert actions[0]["payload"]["statement"] == "Read 24 books this year"
    assert actions[0]["payload"]["priority"] == 4
    # Persona prose still surfaces in the message bubble.
    assert "Got it" in body["response"]


def test_converse_auto_executes_log_progress(authed_client, monkeypatch):
    """log_progress is low-stakes — execute on tool call, no
    confirmation card needed. The response should contain an
    executed_action entry pointing at the new ProgressLog row."""
    from buddy.llm.client import ChatWithToolsResult, OfferedToolCall

    goal = authed_client.post(
        "/goals",
        json={
            "statement": "Read 24 books this year",
            "pace_target_unit": "pages",
            "pace_target_amount": 18,
        },
    ).json()

    async def fake(**kwargs):
        return ChatWithToolsResult(
            text="",  # model emits only tool_use, no prose
            tool_calls=[
                OfferedToolCall(
                    name="log_progress",
                    input={
                        "goal_id": goal["id"],
                        "amount": 30,
                        "unit": "pages",
                        "notes": "morning reading",
                    },
                )
            ],
            model="fake",
            tokens_in=100,
            tokens_out=50,
            cost_usd=0.001,
            raw=None,
        )

    monkeypatch.setattr("buddy.api.converse.chat_with_optional_tools", fake)
    r = authed_client.post("/converse", json={"message": "read 30 pages this morning"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["executed_actions"]) == 1
    assert body["executed_actions"][0]["kind"] == "log_progress"
    assert body["executed_actions"][0]["amount"] == 30
    # Auto-acknowledgment is appended so the user sees confirmation.
    assert "Logged" in body["response"]


def test_converse_anthropic_failure_returns_502(authed_client, monkeypatch):
    """When Anthropic itself fails, surface a 502 with the real error
    text — no opaque 'something went wrong'."""

    async def boom(**_):
        raise RuntimeError("anthropic api: overloaded_error")

    monkeypatch.setattr("buddy.api.converse.chat_with_optional_tools", boom)
    r = authed_client.post("/converse", json={"message": "hi"})
    assert r.status_code == 502
    assert "overloaded_error" in r.text
