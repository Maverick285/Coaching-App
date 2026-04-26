"""Dream tiering classification."""

from __future__ import annotations

from buddy.memory.dreams import classify_kind


def test_pattern_changes_are_auto_apply():
    assert classify_kind("pattern_reinforce") == "auto_apply"
    assert classify_kind("pattern_weaken") == "auto_apply"
    assert classify_kind("pattern_new_high_conf") == "auto_apply"


def test_identity_changes_require_review():
    assert classify_kind("memory_add") == "review"
    assert classify_kind("memory_modify") == "review"
    assert classify_kind("episode_promote") == "review"
    assert classify_kind("persona_calibration") == "review"
    assert classify_kind("pattern_new_low_conf") == "review"


def test_unknown_defaults_to_review():
    assert classify_kind("something_we_have_not_seen") == "review"
