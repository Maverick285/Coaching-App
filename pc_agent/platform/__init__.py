"""Platform adapters for foreground app + idle detection."""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass
class ForegroundSnapshot:
    process_name: str = ""    # bare executable name, e.g. "chrome.exe" or "code"
    window_title: str = ""    # never reported upstream — used only for local debug
    idle_seconds: int = 0     # seconds since last user input (keyboard/mouse)


def get_adapter():
    """Return a platform-appropriate adapter. Raises if unsupported."""
    if sys.platform.startswith("win"):
        from .windows_adapter import WindowsAdapter
        return WindowsAdapter()
    if sys.platform.startswith("linux"):
        from .linux_adapter import LinuxAdapter
        return LinuxAdapter()
    if sys.platform == "darwin":
        from .macos_adapter import MacOSAdapter
        return MacOSAdapter()
    raise RuntimeError(f"Unsupported platform: {sys.platform!r}")
