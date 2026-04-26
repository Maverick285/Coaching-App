"""Shared LLM mocking + helpers for the integration test suite.

Phase 0/1 tests exercise pure-function logic. Phase 2 and 3 endpoints depend
on an Anthropic round trip — those are mocked here so we can verify request
shape, dispatch logic, and persistence without a network hop or API key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock

import pytest


@dataclass
class FakeLLMResult:
    text: str
    model: str = "fake-model"
    tokens_in: int = 100
    tokens_out: int = 50
    cost_usd: float = 0.001
    raw: Any = None


def _canned(text: str) -> FakeLLMResult:
    return FakeLLMResult(text=text)


def fake_chat_returning(*results: FakeLLMResult | str) -> AsyncMock:
    """Build an async mock whose `chat()` returns the supplied results in order.
    Strings are wrapped in a default FakeLLMResult.
    """
    queue: list[FakeLLMResult] = []
    for r in results:
        if isinstance(r, str):
            queue.append(_canned(r))
        else:
            queue.append(r)
    counter = {"i": 0}

    async def _impl(**_: Any) -> FakeLLMResult:
        i = counter["i"]
        if i >= len(queue):
            # Re-emit the last response for any extra calls.
            return queue[-1]
        counter["i"] += 1
        return queue[i]

    mock = AsyncMock(side_effect=_impl)
    return mock


@pytest.fixture
def mock_chat(monkeypatch):
    """Default fixture: `chat()` returns whatever the test stages via patch.

    Tests that need specific responses should call
    `monkeypatch.setattr("buddy.llm.client.chat", fake_chat_returning(...))`
    after this fixture runs.
    """
    default = fake_chat_returning(_canned("{}"))
    monkeypatch.setattr("buddy.llm.client.chat", default)
    return default


@pytest.fixture
def mock_embed(monkeypatch):
    """Embeddings are off in test mode (no OpenAI key)."""

    async def _impl(texts: list[str]) -> tuple[list[list[float]], int, float]:
        return ([[0.0] * 1536 for _ in texts], 0, 0.0)

    monkeypatch.setattr("buddy.llm.client.embed", _impl)


# --- Pre-built canned JSON shapes for the real prompts -----------------------


def capture_classify_response(actions: list[dict[str, Any]], fallback: str = "") -> str:
    return json.dumps({"actions": actions, "fallback_message": fallback})


def woop_response(
    *,
    wish: str,
    outcome: str = "Vivid success scene.",
    obstacles: list[str] | None = None,
    plan: list[str] | None = None,
    intentions: list[dict[str, Any]] | None = None,
    tasks: list[str] | None = None,
    pace_unit: str = "pages",
    pace_amount: float = 18.0,
    pace_description: str = "18 pages per day.",
) -> str:
    return json.dumps(
        {
            "wish": wish,
            "outcome": outcome,
            "obstacles": obstacles or ["A concrete obstacle in current reality."],
            "plan": plan or ["If X happens, then I will Y."],
            "suggested_intentions": intentions or [
                {
                    "cue_type": "obstacle",
                    "cue_text": "I miss a session",
                    "response_text": "Do the smallest version that day.",
                }
            ],
            "suggested_tasks": tasks or ["Open the file", "Read for 5 minutes"],
            "suggested_pace_unit": pace_unit,
            "suggested_pace_amount": pace_amount,
            "suggested_pace_description": pace_description,
        }
    )


def focus_check_in_response(message: str) -> str:
    return json.dumps({"message": message})


def progress_attribution_response(
    attributions: list[dict[str, Any]], unattributed: str = ""
) -> str:
    return json.dumps(
        {"attributions": attributions, "unattributed_text": unattributed}
    )


def consolidation_response(
    *,
    day_summary: str = "Quiet day.",
    auto_apply: list[dict[str, Any]] | None = None,
    review: list[dict[str, Any]] | None = None,
) -> str:
    return json.dumps(
        {
            "day_summary": day_summary,
            "auto_apply": auto_apply or [],
            "review": review or [],
        }
    )


# --- TestClient + auth helper -----------------------------------------------


@pytest.fixture
def authed_client(mock_chat, mock_embed):
    """Yield a TestClient with the bearer token preset on every call."""
    from fastapi.testclient import TestClient

    from buddy.config import reload_settings
    from buddy.main import create_app

    reload_settings()
    app = create_app()
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer test-token"
        yield c
