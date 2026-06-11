"""Pydantic schemas for Phase 4 (PC agent + drift + interventions)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# --- Categories shared by PC agent + Android UsageStats --------------------

# A canonical, intentionally small set. The agent ships with mappings from
# common app/process names to these. The user can add custom rules.
KNOWN_CATEGORIES: tuple[str, ...] = (
    "code_editor",
    "terminal",
    "browser",
    "spreadsheet",
    "document",
    "pdf",
    "communication",      # Slack, Teams, email
    "social_media",       # X, Reddit (where detectable as a desktop app), etc
    "video",              # YouTube apps, VLC, video players
    "music",              # Spotify, music players
    "gaming",
    "system",             # file manager, settings, finder
    "idle",
    "other",
)

AgentSource = Literal["pc_agent", "phone_usage_stats"]


# --- Agent reports ---------------------------------------------------------


class AgentHeartbeat(BaseModel):
    """One report from the PC agent or the phone."""

    source: AgentSource
    foreground_category: str = Field(min_length=1)
    foreground_app_hint: str = ""
    idle_seconds: int = Field(default=0, ge=0)
    active_seconds: int = Field(default=0, ge=0)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class AgentHeartbeatResponse(BaseModel):
    received: bool
    active_session_id: int | None
    interventions_pending: int
    drift_flagged: bool


class AgentStatusResponse(BaseModel):
    """Long-poll target for the PC agent. Tells it whether to keep reporting."""

    active_session_id: int | None
    intention: str | None
    distractor_categories: list[str]
    poll_interval_seconds: int = 10


# --- Distraction rules ----------------------------------------------------


class DistractionRuleCreate(BaseModel):
    goal_id: int
    distractor_category: str
    cooldown_seconds: int = Field(default=90, ge=10, le=3600)


class DistractionRuleOut(BaseModel):
    id: int
    goal_id: int
    distractor_category: str
    cooldown_seconds: int
    is_active: bool


class DistractionRulesListResponse(BaseModel):
    rules: list[DistractionRuleOut]


# --- Interventions --------------------------------------------------------


class InterventionOut(BaseModel):
    id: int
    session_id: int | None
    goal_id: int | None
    tier: int
    fired_at: datetime
    delivered_at: datetime | None
    dismissed_at: datetime | None
    next_escalation_at: datetime | None
    reason: str
    message: str


class InterventionsPendingResponse(BaseModel):
    """Returned to the Android client polling for fresh interventions to render."""

    interventions: list[InterventionOut]


class InterventionAction(BaseModel):
    """Phone tells the backend the user dismissed (or it rendered) the intervention."""

    action: Literal["delivered", "dismissed"]
