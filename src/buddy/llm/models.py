"""Two-tier model resolver. Resolve by tier, not by version string."""

from __future__ import annotations

import json
from enum import Enum
from functools import lru_cache
from pathlib import Path

from buddy.config import get_settings


class ModelTier(str, Enum):
    FAST = "fast"
    REASONING = "reasoning"


_REGISTRY_PATH = Path(__file__).parent / "model_registry.json"


@lru_cache
def _load_registry() -> dict:
    with _REGISTRY_PATH.open() as f:
        return json.load(f)


def reload_registry() -> dict:
    _load_registry.cache_clear()
    return _load_registry()


def resolve_model(tier: ModelTier) -> str:
    """Return the current best model string for the given tier.

    Resolution order:
      1. Pin from settings (BUDDY_FAST_MODEL_PIN / BUDDY_REASONING_MODEL_PIN).
      2. `current` from model_registry.json for the tier.
      3. `fallback` from model_registry.json for the tier.
    """
    settings = get_settings()
    pin = settings.fast_model_pin if tier is ModelTier.FAST else settings.reasoning_model_pin
    if pin:
        return pin
    registry = _load_registry()
    tier_block = registry["tiers"][tier.value]
    return tier_block.get("current") or tier_block["fallback"]


def resolve_embedding_model() -> str:
    settings = get_settings()
    if settings.embedding_model:
        return settings.embedding_model
    return _load_registry()["embedding"]["current"]


def resolve_all_tiers() -> dict[str, str]:
    return {tier.value: resolve_model(tier) for tier in ModelTier}


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    pricing = _load_registry().get("pricing_usd_per_million_tokens", {})
    row = pricing.get(model)
    if row is None:
        # Unknown model: skip pricing rather than guess
        return 0.0
    return (tokens_in * row.get("input", 0.0) + tokens_out * row.get("output", 0.0)) / 1_000_000
