"""Pydantic request/response models for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# --- Health ---------------------------------------------------------------


class DailyRhythm(BaseModel):
    timezone: str
    morning_hour: int
    morning_minute: int
    end_of_day_hour: int
    end_of_day_minute: int


class ScheduledJob(BaseModel):
    id: str
    next_run_at: str | None = None
    trigger: str = ""


class DiagnosticsBlock(BaseModel):
    last_consolidation_at: str | None = None
    last_consolidation_status: str | None = None
    last_backup_push_at: str | None = None
    last_backup_push_status: str | None = None
    last_engine_tick_at: str | None = None
    last_engine_tick_fired: str | None = None
    sms_configured: bool = False
    git_remote_configured: bool = False
    scheduled_jobs: list[ScheduledJob] = []


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    db_connected: bool
    memory_repo_status: str
    models_resolved: dict[str, str]
    daily_rhythm: DailyRhythm | None = None
    diagnostics: DiagnosticsBlock | None = None


class ProfileResponse(BaseModel):
    user_name: str
    persona_name: str
    timezone: str
    onboarding_complete: bool
    has_persona_md: bool
    has_memory_md: bool
    chat_tier: Literal["auto", "fast", "reasoning"] = "auto"


class ProfileUpdate(BaseModel):
    user_name: str | None = None
    persona_name: str | None = None
    timezone: str | None = None
    chat_tier: Literal["auto", "fast", "reasoning"] | None = None


# --- Converse -------------------------------------------------------------


class ConverseRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1)
    force_reasoning_tier: bool = False
    # Optional client-supplied workflow boundary tag. When None, the
    # backend derives it from the daily-rhythm clock + active-session
    # state. Allowed labels (informational): morning_check_in,
    # end_of_day, weekly_review_window, post_focus, post_failure,
    # mid_task, mid_focus_session.
    boundary_context: str | None = None


class MemoryLoadedItem(BaseModel):
    file: str
    reason: str
    score: float | None = None


class ConverseResponse(BaseModel):
    session_id: str
    message_id: str
    response: str
    model_used: str
    tokens_in: int
    tokens_out: int
    cost_estimate: float
    memory_loaded: list[MemoryLoadedItem]


# --- Memory ---------------------------------------------------------------


class MemoryFileMeta(BaseModel):
    path: str
    document_type: str
    bytes: int
    last_modified: datetime
    indexed: bool


class MemoryFilesResponse(BaseModel):
    files: list[MemoryFileMeta]


class MemoryFileContent(BaseModel):
    path: str
    content: str
    last_modified: datetime


class MemoryFileWrite(BaseModel):
    content: str
    commit_message: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    include_chunks: bool = True


class SearchHit(BaseModel):
    document_path: str
    chunk_index: int
    content: str | None
    score: float
    bm25_score: float | None = None
    vector_score: float | None = None


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


# --- Dreams ---------------------------------------------------------------


class DreamProposal(BaseModel):
    id: str
    proposal_kind: str
    target_path: str
    summary: str
    proposed_content: str
    rationale: str
    status: str
    created_at: datetime


class DreamsResponse(BaseModel):
    pending: list[DreamProposal]
    auto_applied_recent: list[DreamProposal]


class DreamAction(BaseModel):
    action: Literal["approve", "reject", "edit"]
    proposal_id: str
    edited_content: str | None = None


class DreamActionResponse(BaseModel):
    proposal_id: str
    new_status: str
    applied_path: str | None = None


# --- Explain --------------------------------------------------------------


class ExplainRequest(BaseModel):
    session_id: str
    message_id: str


class ExplainResponse(BaseModel):
    session_id: str
    message_id: str
    memory_loaded: list[MemoryLoadedItem]
    full_context: str | None = None


# --- Conversations --------------------------------------------------------


class ConversationSummary(BaseModel):
    session_id: str
    started_at: datetime
    last_message_at: datetime
    title: str
    message_count: int


class ConversationsResponse(BaseModel):
    sessions: list[ConversationSummary]


class ConversationMessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    model_used: str


class ConversationDetail(BaseModel):
    session_id: str
    started_at: datetime
    title: str
    messages: list[ConversationMessageOut]


# --- Usage ----------------------------------------------------------------


class UsageBucket(BaseModel):
    label: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


class UsageResponse(BaseModel):
    today: UsageBucket
    month_to_date: UsageBucket
    last_7_days: UsageBucket
    by_model: list[UsageBucket]
    soft_cap_usd: float
    hard_cap_usd: float
    soft_cap_exceeded: bool
    hard_cap_exceeded: bool


# --- Intake ---------------------------------------------------------------


class IntakeOption(BaseModel):
    id: str
    label: str
    body: str | None = None  # only for pair_choice


class IntakeQuestion(BaseModel):
    """One typed question shipped to the client.

    Kind drives which renderer the client uses:
      text_short  — single-line input
      text_long   — multi-line input
      pair_choice — A vs B (options is exactly 2)
      scale       — 5-point scale; scale_low / scale_high label the ends
      multi_choice — pick zero or more from options
    """

    key: str
    kind: str
    prompt: str
    axis: str = ""
    optional: bool = False
    options: list[IntakeOption] | None = None
    scale_low: str | None = None
    scale_high: str | None = None


class IntakeStartResponse(BaseModel):
    intake_id: str
    question: IntakeQuestion | None
    step: int
    total_steps: int


class IntakeTurnRequest(BaseModel):
    intake_id: str
    # Typed answer payload. Shape depends on the question kind:
    #   text_short / text_long → {"text": "..."}
    #   pair_choice            → {"id": "matter_of_fact"}
    #   scale                  → {"value": 3}
    #   multi_choice           → {"selected": ["sleep", "exercise"]}
    answer: dict[str, Any] = Field(default_factory=dict)


class IntakeTurnResponse(BaseModel):
    intake_id: str
    question: IntakeQuestion | None
    step: int
    total_steps: int
    finished: bool


class IntakeFinalizeRequest(BaseModel):
    intake_id: str


class IntakeFinalizeResponse(BaseModel):
    intake_id: str
    persona_md: str
    memory_md: str


# --- Clone ----------------------------------------------------------------


class CloneInstructionsResponse(BaseModel):
    git_remote: str
    instructions: str


# --- Errors ---------------------------------------------------------------


class ErrorResponse(BaseModel):
    error: str
    detail: str | Any | None = None
