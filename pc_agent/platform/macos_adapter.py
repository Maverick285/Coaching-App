"""macOS foreground + idle detection.

Best-effort, no extra packages: shells out to AppleScript via `osascript`
for the foreground app name, and to `ioreg` for idle seconds. Both are
preinstalled on every Mac. If you want a more robust path later, install
pyobjc and use Cocoa's NSWorkspace + CGEventSourceSecondsSinceLastEventType.
"""

from __future__ import annotations

import re
import subprocess

from . import ForegroundSnapshot

_FOREGROUND_SCRIPT = (
    'tell application "System Events" to get name of first application process whose frontmost is true'
)


class MacOSAdapter:
    name = "macos"

    def snapshot(self) -> ForegroundSnapshot:
        try:
            name = subprocess.check_output(
                ["osascript", "-e", _FOREGROUND_SCRIPT], text=True, timeout=2
            ).strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            name = ""
        return ForegroundSnapshot(
            process_name=name,
            window_title="",
            idle_seconds=self._idle_seconds(),
        )

    def _idle_seconds(self) -> int:
        try:
            out = subprocess.check_output(
                ["ioreg", "-c", "IOHIDSystem"], text=True, timeout=2
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return 0
        m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out)
        if not m:
            return 0
        # HIDIdleTime is in nanoseconds.
        return int(m.group(1)) // 1_000_000_000
