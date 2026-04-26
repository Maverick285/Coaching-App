"""Tier selection for /converse calls.

Most messages route to FAST. The REASONING tier is invoked only when
the operation actually benefits from it.
"""

from __future__ import annotations

import re

from buddy.llm.models import ModelTier

_PLANNING_PATTERNS = [
    r"\bhelp me plan\b",
    r"\blet'?s figure out\b",
    r"\bWOOP\b",
    r"\bwhat should i do about\b",
    r"\bi'?m stuck on\b",
    r"\bplan this\b",
    r"\bpre-?mortem\b",
]

_INTROSPECTION_PATTERNS = [
    r"\bwhat do you (know|remember) about me\b",
    r"\bwhy did you say that\b",
    r"\bexplain your (reasoning|thinking)\b",
    r"\bwhat have you (learned|noticed) about me\b",
]


def select_tier(
    *,
    message: str,
    force_reasoning: bool = False,
    operation: str = "converse",
) -> ModelTier:
    if force_reasoning:
        return ModelTier.REASONING
    if operation in {"intake", "consolidation", "pattern_synthesis", "dream_promotion"}:
        return ModelTier.REASONING
    if len(message) > 500:
        return ModelTier.REASONING
    lowered = message.lower()
    for pat in _PLANNING_PATTERNS + _INTROSPECTION_PATTERNS:
        if re.search(pat, lowered):
            return ModelTier.REASONING
    return ModelTier.FAST
