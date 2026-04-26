"""Pydantic request/response schemas for Phase 3 (capture + focus sessions)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# --- Capture ---------------------------------------------------------------

CaptureKind = Literal[
    "log_progress",
    "create_task",
    "create_goal",
    "journal_note",
    "reminder",
    "quick_question",
    "start_focus",
    "unknown",
]


class CaptureAction(BaseModel):
    """A single proposed action the user can confirm or reject."""

    kind: CaptureKind
    summary: str  # human-readable confirmation, e.g. "Log 18 pages on Reading."
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class CaptureRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    source: str = "manual"  # manual | voice | widget


class CaptureResponse(BaseModel):
    capture_id: int
    raw_text: str
    actions: list[CaptureAction]
    fallback_message: str = ""  # when classification confidence is low


class CaptureConfirm(BaseModel):
    capture_id: int
    actions: list[CaptureAction]


class DispatchResultItem(BaseModel):
    kind: CaptureKind
    success: bool
    detail: str = ""
    created_id: int | None = None


class CaptureDispatchResponse(BaseModel):
    capture_id: int
    results: list[DispatchResultItem]


# --- Focus sessions --------------------------------------------------------

FocusState = Literal["active", "completed", "abandoned"]
FocusCheckInKind = Literal["presence", "mid", "end", "drift"]


class FocusStart(BaseModel):
    intention: str = Field(min_length=1, max_length=500)
    planned_duration_minutes: int = Field(default=45, ge=5, le=240)
    goal_id: int | None = None


class FocusEnd(BaseModel):
    summary: str = ""
    state: FocusState = "completed"


class FocusCheckInOut(BaseModel):
    id: int
    session_id: int
    fired_at: datetime
    kind: FocusCheckInKind
    message: str
    user_response: str


class FocusCheckInResponse(BaseModel):
    """Returned when the client requests the next check-in text."""

    check_in: FocusCheckInOut


class FocusCheckInUserReply(BaseModel):
    """Optional: user replied to a check-in."""

    response: str


class FocusSessionOut(BaseModel):
    id: int
    goal_id: int | None
    intention: str
    started_at: datetime
    planned_duration_minutes: int
    ended_at: datetime | None
    state: FocusState
    summary: str
    interventions_fired: int


class FocusSessionDetail(BaseModel):
    session: FocusSessionOut
    check_ins: list[FocusCheckInOut]


class FocusActiveResponse(BaseModel):
    session: FocusSessionOut | None
