"""Tier router invariants."""

from __future__ import annotations

from buddy.llm.models import ModelTier
from buddy.llm.router import select_tier


def test_short_routine_message_routes_fast():
    assert select_tier(message="quick log: read 30 pages") is ModelTier.FAST


def test_force_reasoning_overrides_everything():
    assert (
        select_tier(message="hi", force_reasoning=True) is ModelTier.REASONING
    )


def test_long_message_routes_reasoning():
    long = "x " * 300
    assert select_tier(message=long) is ModelTier.REASONING


def test_planning_phrase_routes_reasoning():
    assert (
        select_tier(message="help me plan the runsheet review for Friday")
        is ModelTier.REASONING
    )


def test_introspection_routes_reasoning():
    assert (
        select_tier(message="what do you know about me right now?")
        is ModelTier.REASONING
    )


def test_consolidation_operation_always_reasoning():
    assert (
        select_tier(message="...", operation="consolidation")
        is ModelTier.REASONING
    )
