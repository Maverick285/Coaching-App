"""Par-1 grading unit tests."""

from __future__ import annotations

from buddy.services.grading import _per_goal_score, _priority_weighted_avg


def test_per_goal_score_below_pace():
    assert _per_goal_score(progress=9.0, pace_target=18.0) == 0.5


def test_per_goal_score_at_pace():
    assert _per_goal_score(progress=18.0, pace_target=18.0) == 1.0


def test_per_goal_score_above_pace_uncapped():
    assert _per_goal_score(progress=27.0, pace_target=18.0) == 1.5


def test_per_goal_score_zero_progress_zero():
    assert _per_goal_score(progress=0.0, pace_target=18.0) == 0.0


def test_pace_target_zero_falls_back_to_binary():
    assert _per_goal_score(progress=1.0, pace_target=0.0) == 1.0
    assert _per_goal_score(progress=0.0, pace_target=0.0) == 0.0


def test_priority_weighting_pulls_average_toward_high_priority():
    # Low-priority goal at 0.0, high-priority goal at 1.0.
    avg = _priority_weighted_avg([(0.0, 1), (1.0, 5)])
    assert avg == 5.0 / 6.0


def test_priority_weighting_unanimous():
    avg = _priority_weighted_avg([(1.0, 3), (1.0, 5)])
    assert avg == 1.0


def test_priority_weighting_empty():
    assert _priority_weighted_avg([]) == 0.0
