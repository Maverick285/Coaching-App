"""Agent loop: poll backend status, report when a session is active.

Lifecycle:

    while True:
        status = GET /agent/status
        if status.active_session_id is None:
            sleep(poll_interval)   # silent
            continue
        snap = adapter.snapshot()
        category = categorize(snap.process_name)
        POST /agent/heartbeat { source: pc_agent, foreground_category, … }
        sleep(report_interval)

The agent never sends window_title or any process arg upstream. Only the
canonical category and a coarse process name (so the user can later
categorize unknown apps from the CLI).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from . import __version__
from .categories import categorize
from .platform import ForegroundSnapshot, get_adapter

log = logging.getLogger("buddy.agent")


@dataclass
class AgentConfig:
    backend_url: str
    auth_token: str
    poll_interval_seconds: int = 10
    report_interval_seconds: int = 10
    request_timeout_seconds: float = 10.0


class Agent:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.adapter = get_adapter()
        self._client = httpx.Client(
            base_url=config.backend_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {config.auth_token}",
                "User-Agent": f"buddy-pc-agent/{__version__}",
                "Accept": "application/json",
            },
            timeout=config.request_timeout_seconds,
        )
        self._distractor_categories: set[str] = set()
        self._active_session_id: int | None = None

    # ---- one tick -------------------------------------------------------

    def status(self) -> tuple[int | None, set[str], int]:
        """Returns (active_session_id, distractor_categories, poll_interval)."""
        try:
            r = self._client.get("/agent/status")
            r.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("status request failed: %s", exc)
            return (None, set(), self.config.poll_interval_seconds)
        body = r.json()
        return (
            body.get("active_session_id"),
            set(body.get("distractor_categories") or []),
            int(body.get("poll_interval_seconds") or self.config.poll_interval_seconds),
        )

    def report(self, snap: ForegroundSnapshot, category: str, *, active_seconds: int) -> dict[str, Any]:
        payload = {
            "source": "pc_agent",
            "foreground_category": category,
            "foreground_app_hint": snap.process_name or "",
            "idle_seconds": int(snap.idle_seconds),
            "active_seconds": int(active_seconds),
            "raw_payload": {"platform": self.adapter.name},
        }
        r = self._client.post("/agent/heartbeat", json=payload)
        r.raise_for_status()
        return r.json()

    # ---- main loop ------------------------------------------------------

    def run_forever(self, max_ticks: int | None = None) -> None:
        log.info("agent started (platform=%s)", self.adapter.name)
        last_report_at = 0.0
        ticks = 0
        while True:
            ticks += 1
            if max_ticks is not None and ticks > max_ticks:
                return
            session_id, distractors, poll_interval = self.status()
            self._active_session_id = session_id
            self._distractor_categories = distractors

            if session_id is None:
                # No active session — stay silent.
                time.sleep(poll_interval)
                continue

            snap = self.adapter.snapshot()
            category = categorize(snap.process_name) if snap.process_name else "idle"
            if snap.idle_seconds >= 60 and category != "idle":
                # Idle takes precedence so drift doesn't fire while AFK.
                category = "idle"

            now = time.time()
            active_seconds = (
                int(now - last_report_at) if last_report_at else self.config.report_interval_seconds
            )
            try:
                resp = self.report(snap, category, active_seconds=active_seconds)
            except httpx.HTTPError as exc:
                log.warning("heartbeat failed: %s", exc)
            else:
                if resp.get("drift_flagged"):
                    log.info(
                        "drift flagged (category=%s, hint=%s)",
                        category,
                        snap.process_name,
                    )
            last_report_at = now
            time.sleep(self.config.report_interval_seconds)

    def close(self) -> None:
        self._client.close()
