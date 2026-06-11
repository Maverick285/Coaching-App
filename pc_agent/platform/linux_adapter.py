"""Linux foreground + idle detection.

Two paths, autodetected:
  - X11: shell out to `xdotool` (foreground) and `xprintidle` (idle ms).
    Both are widely packaged. Falls back gracefully if unavailable.
  - Wayland: most compositors don't expose foreground without protocol-
    specific calls; we report process_name='' and skip rather than guess.
    The agent is best-effort: missing data just means no drift signal.

To install on Debian/Ubuntu:
    sudo apt install xdotool xprintidle
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from . import ForegroundSnapshot


def _is_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def _process_name_from_pid(pid: int) -> str:
    try:
        with Path(f"/proc/{pid}/comm").open() as f:
            return f.read().strip()
    except OSError:
        return ""


class LinuxAdapter:
    name = "linux"

    def __init__(self) -> None:
        self._has_xdotool = shutil.which("xdotool") is not None
        self._has_xprintidle = shutil.which("xprintidle") is not None
        self._wayland = _is_wayland()

    def snapshot(self) -> ForegroundSnapshot:
        if self._wayland or not self._has_xdotool:
            return ForegroundSnapshot(idle_seconds=self._idle_seconds())

        try:
            wid = subprocess.check_output(
                ["xdotool", "getactivewindow"], text=True, timeout=2
            ).strip()
            title = subprocess.check_output(
                ["xdotool", "getwindowname", wid], text=True, timeout=2
            ).strip()
            pid_str = subprocess.check_output(
                ["xdotool", "getwindowpid", wid], text=True, timeout=2
            ).strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return ForegroundSnapshot(idle_seconds=self._idle_seconds())

        process_name = ""
        if pid_str.isdigit():
            process_name = _process_name_from_pid(int(pid_str))

        return ForegroundSnapshot(
            process_name=process_name,
            window_title=title,
            idle_seconds=self._idle_seconds(),
        )

    def _idle_seconds(self) -> int:
        if self._wayland or not self._has_xprintidle:
            return 0
        try:
            ms = subprocess.check_output(["xprintidle"], text=True, timeout=2).strip()
            return int(ms) // 1000 if ms.isdigit() else 0
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return 0
