"""Proactive surfacing boundary detection (master spec §5.11 + §53)."""

from __future__ import annotations

from datetime import datetime, timedelta

from buddy.llm.prompts.persona import is_boundary_now


def _at(hour: int, weekday: int = 1) -> datetime:
    """2026-04-28 is a Tuesday (weekday=1). Add days to reach the target."""
    base = datetime(2026, 4, 28, hour, 0, 0)
    delta = (weekday - base.weekday()) % 7
    return base + timedelta(days=delta)


def test_active_focus_session_disables_proactive():
    ok, label = is_boundary_now(
        boundary_context=None,
        now=_at(15),
        morning_hour=7,
        end_of_day_hour=21,
        active_focus=True,
    )
    assert not ok
    assert label == "mid_focus_session"


def test_morning_window_enables_proactive():
    ok, label = is_boundary_now(
        boundary_context=None,
        now=_at(7),
        morning_hour=7,
        end_of_day_hour=21,
        active_focus=False,
    )
    assert ok
    assert label == "morning_check_in"


def test_eod_window_enables_proactive():
    ok, label = is_boundary_now(
        boundary_context=None,
        now=_at(21),
        morning_hour=7,
        end_of_day_hour=21,
        active_focus=False,
    )
    assert ok
    assert label == "end_of_day"


def test_random_midday_disables_proactive():
    ok, label = is_boundary_now(
        boundary_context=None,
        now=_at(14),
        morning_hour=7,
        end_of_day_hour=21,
        active_focus=False,
    )
    assert not ok
    assert label == "mid_task"


def test_explicit_client_override_wins():
    ok, label = is_boundary_now(
        boundary_context="post_focus",
        now=_at(14),
        morning_hour=7,
        end_of_day_hour=21,
        active_focus=False,
    )
    assert ok
    assert label == "post_focus"


def test_sunday_evening_is_weekly_review():
    ok, label = is_boundary_now(
        boundary_context=None,
        now=_at(19, weekday=6),  # Sunday
        morning_hour=7,
        end_of_day_hour=21,
        active_focus=False,
    )
    assert ok
    assert label == "weekly_review_window"
