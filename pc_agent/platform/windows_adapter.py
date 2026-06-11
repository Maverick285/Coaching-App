"""Windows foreground + idle detection.

Uses ctypes against user32 + kernel32 so we don't need pywin32. Tested
against Windows 10 + 11.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import os

from . import ForegroundSnapshot


class WindowsAdapter:
    name = "windows"

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32
        self._psapi = ctypes.windll.psapi

    def snapshot(self) -> ForegroundSnapshot:
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return ForegroundSnapshot(process_name="", window_title="", idle_seconds=self._idle_seconds())

        # Window title.
        length = self._user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or ""

        # Owning process.
        pid = ctypes.wintypes.DWORD()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        proc_name = ""
        if pid.value:
            handle = self._kernel32.OpenProcess(
                0x0410, False, pid.value  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
            )
            if handle:
                try:
                    name_buf = ctypes.create_unicode_buffer(260)
                    if self._psapi.GetModuleBaseNameW(handle, None, name_buf, 260):
                        proc_name = name_buf.value
                finally:
                    self._kernel32.CloseHandle(handle)

        return ForegroundSnapshot(
            process_name=proc_name or "",
            window_title=title,
            idle_seconds=self._idle_seconds(),
        )

    def _idle_seconds(self) -> int:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.wintypes.UINT),
                ("dwTime", ctypes.wintypes.DWORD),
            ]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not self._user32.GetLastInputInfo(ctypes.byref(info)):
            return 0
        tick = self._kernel32.GetTickCount()
        return max(0, (tick - info.dwTime) // 1000)
