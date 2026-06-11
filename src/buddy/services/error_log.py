"""Last-N unhandled-exception ring buffer.

Built specifically to give the user a way to read real error tracebacks
from the app when something 500s, without SSHing into the box. Every
unhandled exception that escapes a request handler gets captured here
with method/path/status/traceback and is retrievable via
GET /admin/errors. The Customize screen renders the most recent.

Capacity is small (20) — this is for live debugging, not analytics.
The buffer lives in-process so it resets on every restart, which is
exactly what we want.
"""

from __future__ import annotations

import threading
import traceback
from collections import deque
from datetime import datetime
from typing import Any

_LOCK = threading.Lock()
_BUFFER: deque[dict[str, Any]] = deque(maxlen=20)


def record(*, method: str, path: str, exc: BaseException, status: int = 500) -> None:
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "method": method,
        "path": path,
        "status": status,
        "exception": f"{type(exc).__name__}: {exc}",
        "traceback": tb[-4000:],  # tail; full TBs can be huge
    }
    with _LOCK:
        _BUFFER.appendleft(entry)


def snapshot() -> list[dict[str, Any]]:
    with _LOCK:
        return list(_BUFFER)


def clear() -> None:
    with _LOCK:
        _BUFFER.clear()
