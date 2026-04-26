"""CLI config loading from ~/.config/buddy/config.toml or env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import tomli

CONFIG_PATH = Path.home() / ".config" / "buddy" / "config.toml"


@dataclass
class CLIConfig:
    backend_url: str
    auth_token: str
    editor: str = "vi"


def load_cli_config() -> CLIConfig:
    backend = os.environ.get("BUDDY_BACKEND_URL", "")
    token = os.environ.get("BUDDY_AUTH_TOKEN", "")
    editor = os.environ.get("EDITOR", "vi")

    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("rb") as f:
            data = tomli.load(f)
        backend = backend or data.get("backend_url", "")
        token = token or data.get("auth_token", "")
        editor = data.get("editor", editor)

    if not backend or not token:
        raise SystemExit(
            "Missing CLI config. Either set BUDDY_BACKEND_URL + BUDDY_AUTH_TOKEN env vars, "
            f"or create {CONFIG_PATH} with backend_url + auth_token."
        )
    return CLIConfig(backend_url=backend.rstrip("/"), auth_token=token, editor=editor)
