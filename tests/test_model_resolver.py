"""Model tier resolver returns current-latest unless pinned."""

from __future__ import annotations

from buddy.config import reload_settings
from buddy.llm.models import ModelTier, resolve_all_tiers, resolve_model


def test_default_resolution_returns_current():
    tiers = resolve_all_tiers()
    assert tiers["fast"].startswith("claude-sonnet")
    assert tiers["reasoning"].startswith("claude-opus")


def test_pin_overrides_registry(monkeypatch):
    monkeypatch.setenv("BUDDY_FAST_MODEL_PIN", "claude-haiku-9-9-pinned")
    monkeypatch.setenv("BUDDY_REASONING_MODEL_PIN", "claude-opus-9-9-pinned")
    reload_settings()
    assert resolve_model(ModelTier.FAST) == "claude-haiku-9-9-pinned"
    assert resolve_model(ModelTier.REASONING) == "claude-opus-9-9-pinned"
