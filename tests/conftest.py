from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "cli"))


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Every test gets its own data + memory directory and config."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("BUDDY_DB_PATH", str(data / "buddy.db"))
    monkeypatch.setenv("BUDDY_MEMORY_PATH", str(data / "memory"))
    monkeypatch.setenv("BUDDY_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("BUDDY_USER_NAME", "Tester")
    monkeypatch.setenv("BUDDY_PERSONA_NAME", "Coach")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("BUDDY_FAST_MODEL_PIN", "")
    monkeypatch.setenv("BUDDY_REASONING_MODEL_PIN", "")
    # Force a fresh settings object.
    from buddy.config import reload_settings

    reload_settings()
    yield
    reload_settings()
