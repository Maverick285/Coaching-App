"""Process-name → category mapping. Loads default_map.json plus an optional
user override at ~/.config/buddy-agent/categories.json (whose keys overlay
the defaults)."""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_MAP_PATH = Path(__file__).parent / "default_map.json"
USER_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "buddy-agent"
USER_MAP_PATH = USER_CONFIG_DIR / "categories.json"

# Local copy of the canonical category set so the agent doesn't have to
# depend on the `buddy` library at runtime. Must stay in sync with
# src/buddy/schemas_phase4.py::KNOWN_CATEGORIES.
KNOWN_CATEGORIES_FALLBACK: tuple[str, ...] = (
    "code_editor",
    "terminal",
    "browser",
    "spreadsheet",
    "document",
    "pdf",
    "communication",
    "social_media",
    "video",
    "music",
    "gaming",
    "system",
    "idle",
    "other",
)


def _load_one(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    with path.open() as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, list)}


def load_category_map() -> dict[str, str]:
    """Returns {process_name_lower: category}. User entries win on conflict."""
    out: dict[str, str] = {}
    for category, names in _load_one(DEFAULT_MAP_PATH).items():
        for n in names:
            out[n.lower()] = category
    for category, names in _load_one(USER_MAP_PATH).items():
        for n in names:
            out[n.lower()] = category
    return out


def categorize(process_name: str, fallback: str = "other") -> str:
    """Map a process executable name (e.g. 'chrome.exe' or 'code') to a
    canonical category. Returns `fallback` if unknown."""
    if not process_name:
        return fallback
    name = process_name.strip().lower()
    mp = load_category_map()
    if name in mp:
        return mp[name]
    # Try without extension.
    if "." in name:
        base = name.rsplit(".", 1)[0]
        if base in mp:
            return mp[base]
    return fallback


def add_user_mapping(process_name: str, category: str) -> None:
    """Append (or override) a single mapping in the user config."""
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing: dict[str, list[str]] = {}
    if USER_MAP_PATH.exists():
        with USER_MAP_PATH.open() as f:
            existing = json.load(f)
    bucket = existing.setdefault(category, [])
    if process_name.lower() not in [b.lower() for b in bucket]:
        bucket.append(process_name)
    with USER_MAP_PATH.open("w") as f:
        json.dump(existing, f, indent=2)
