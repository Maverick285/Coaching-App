"""PC agent: categorization + episode duration math."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace


def test_categorize_known_executable():
    from pc_agent.categories import categorize

    assert categorize("chrome.exe") == "browser"
    assert categorize("Code") == "code_editor"
    assert categorize("slack.exe") == "communication"
    assert categorize("vlc") == "video"


def test_categorize_strips_extension_for_lookup():
    from pc_agent.categories import categorize

    # "chrome" without .exe also resolves to browser via the bare lookup.
    assert categorize("chrome") == "browser"


def test_categorize_unknown_falls_back_to_other():
    from pc_agent.categories import categorize

    assert categorize("RogueCoolApp.exe") == "other"
    assert categorize("") == "other"


def test_known_categories_match_backend_taxonomy():
    """If this drifts, the agent will report categories the backend
    doesn't know about."""
    from pc_agent.categories import KNOWN_CATEGORIES_FALLBACK
    from buddy.schemas_phase4 import KNOWN_CATEGORIES

    assert set(KNOWN_CATEGORIES_FALLBACK) == set(KNOWN_CATEGORIES)


def test_episode_duration_single_recent_report_uses_active_seconds():
    from buddy.services.interventions import _episode_duration

    now = datetime.utcnow()
    reports = [
        SimpleNamespace(
            received_at=now,
            foreground_category="social_media",
            active_seconds=120,
        )
    ]
    seconds, cat, last_at = _episode_duration(reports, {"social_media"})
    assert cat == "social_media"
    assert seconds >= 120


def test_episode_duration_breaks_on_category_change():
    from buddy.services.interventions import _episode_duration

    now = datetime.utcnow()
    reports = [
        SimpleNamespace(
            received_at=now - timedelta(seconds=200),
            foreground_category="social_media",
            active_seconds=10,
        ),
        SimpleNamespace(
            received_at=now - timedelta(seconds=180),
            foreground_category="code_editor",
            active_seconds=10,
        ),
        SimpleNamespace(
            received_at=now,
            foreground_category="social_media",
            active_seconds=10,
        ),
    ]
    # Only the latest run counts. The latest report is in social_media,
    # the previous report (180s ago) is code_editor — so the run = the
    # last report's active_seconds (10) plus zero gap (no prior contiguous
    # report).
    seconds, cat, _ = _episode_duration(reports, {"social_media"})
    assert cat == "social_media"
    assert seconds == 10


def test_episode_duration_ignores_non_distractor_latest():
    from buddy.services.interventions import _episode_duration

    now = datetime.utcnow()
    reports = [
        SimpleNamespace(
            received_at=now,
            foreground_category="code_editor",
            active_seconds=30,
        )
    ]
    seconds, cat, _ = _episode_duration(reports, {"social_media"})
    assert cat is None
    assert seconds == 0
