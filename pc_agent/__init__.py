"""Buddy PC activity agent.

Tiny background process that, while a focus session is active on the
backend, reports the user's foreground app category + idle state every
~10 seconds. Outside active sessions, it stays silent.

Per spec §2.2:
  - Reports categories, never content.
  - No keystroke logging, no screen capture, no document/URL specifics.
  - Opt-in per session: the agent doesn't decide when to start
    reporting — the backend's /agent/status tells it.
"""

__version__ = "0.1.0"
