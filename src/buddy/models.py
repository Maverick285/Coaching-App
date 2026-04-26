"""SQLAlchemy ORM models for the search index and ancillary tables.

Note: FTS5 and sqlite-vec virtual tables are created via raw SQL in
`buddy.memory.index.bootstrap_index_schema()` rather than ORM-mapped here,
because SQLAlchemy doesn't model virtual tables cleanly.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from buddy.db import Base


class IndexedDocument(Base):
    __tablename__ = "indexed_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_indexed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("document_path", "chunk_index", name="uq_doc_chunk"),
    )


class ApiUsage(Base):
    __tablename__ = "api_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class MemoryProposal(Base):
    """DB companion to DREAMS.md for programmatic access."""

    __tablename__ = "memory_proposals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # uuid string
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    proposal_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    target_path: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_content: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )  # pending | approved | rejected | auto_applied
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    proposal_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )


class Conversation(Base):
    __tablename__ = "conversations"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    title: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    log_path: Mapped[str] = mapped_column(String(512), default="", nullable=False)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # uuid
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    memory_loaded: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )


class IntakeSession(Base):
    __tablename__ = "intake_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    transcript: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )


# --- Phase 2: goals, tasks, intentions, journal, par-1 grading -------------


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    timeframe: Mapped[str] = mapped_column(
        String(32), default="open_ended", nullable=False
    )  # open_ended | deadline | recurring
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)  # 1..5
    approach: Mapped[str] = mapped_column(
        String(32), default="user_driven", nullable=False
    )  # user_driven | system_assisted | hybrid
    plan_source: Mapped[str] = mapped_column(
        String(32), default="user_plan", nullable=False
    )  # user_plan | system_plan | no_plan
    state: Mapped[str] = mapped_column(
        String(16), default="active", nullable=False, index=True
    )  # proposed | active | paused | completed | abandoned
    intervention_ceiling: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    pace_target_unit: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    pace_target_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    pace_target_description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    mvp_threshold: Mapped[str] = mapped_column(Text, default="", nullable=False)
    parent_goal_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    reflection_log: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    definition_of_done: Mapped[str] = mapped_column(Text, default="", nullable=False)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    triggering_intention_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state: Mapped[str] = mapped_column(
        String(16), default="proposed", nullable=False, index=True
    )  # proposed | scheduled | in_progress | done | skipped
    first_60_seconds: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ImplementationIntention(Base):
    __tablename__ = "implementation_intentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    cue_type: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # time_place | routine | event | obstacle
    cue_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class ProgressLog(Base):
    __tablename__ = "progress_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    attributed_units: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    unit_label: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    source: Mapped[str] = mapped_column(
        String(16), default="manual", nullable=False
    )  # manual | voice | pc_agent | usage_stats | system
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)


class DayGrade(Base):
    __tablename__ = "day_grades"

    grade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    system_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    user_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    per_goal_scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    user_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_zero_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    entry_date: Mapped[date] = mapped_column(Date, primary_key=True)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    mood: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


# --- Phase 3: focus sessions, capture ---------------------------------------


class FocusSession(Base):
    __tablename__ = "focus_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    intention: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    planned_duration_minutes: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    state: Mapped[str] = mapped_column(
        String(16), default="active", nullable=False, index=True
    )  # active | completed | abandoned
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    interventions_fired: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class FocusCheckIn(Base):
    __tablename__ = "focus_check_ins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    fired_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    kind: Mapped[str] = mapped_column(
        String(16), default="presence", nullable=False
    )  # presence | mid | end | drift
    message: Mapped[str] = mapped_column(Text, nullable=False)
    user_response: Mapped[str] = mapped_column(Text, default="", nullable=False)


class CaptureLog(Base):
    """Audit trail for /capture invocations."""

    __tablename__ = "capture_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_actions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)


# --- Phase 4: PC agent reports + interventions + distraction rules ---------


class AgentReport(Base):
    """One heartbeat from the PC agent (or the phone's UsageStats)."""

    __tablename__ = "agent_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # pc_agent | phone_usage_stats
    foreground_category: Mapped[str] = mapped_column(String(64), nullable=False)
    foreground_app_hint: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    idle_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Intervention(Base):
    """A single intervention fired by the engine.

    Lifecycle:
        fired_at  → notification dispatched to the device
        delivered_at  → device acknowledged render
        dismissed_at  → user tapped dismiss (or session ended)
        next_escalation_at → if still un-dismissed at this moment, fire the next tier
    """

    __tablename__ = "interventions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    goal_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    tier: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 / 1 / 2
    fired_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_escalation_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reason: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)


class DistractionRule(Base):
    """Per-goal: which categories count as distraction during this goal's
    sessions, and how long the user can be in that category before the
    engine fires Tier 0."""

    __tablename__ = "distraction_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    distractor_category: Mapped[str] = mapped_column(String(64), nullable=False)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class BlockedAppRule(Base):
    """Per-goal: which packages are friction (Tier 3) or hard-blocked
    (Tier 4) when the goal's session is active.

    Block tier semantics:
        3 — Friction: 60s overlay with reason field; user can proceed.
        4 — Hard block: app is force-redirected to launcher until
            session ends or override is redeemed.
    """

    __tablename__ = "blocked_app_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    package_name: Mapped[str] = mapped_column(String(256), nullable=False)
    block_tier: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class OverrideRequest(Base):
    """One override request: user wants to bypass a Tier 3 / Tier 4 block.

    Lifecycle:
      pending  → SMS sent to approver with one-time code
      approved → user entered the code; window of `active_minutes` opens
      expired  → window closed, blocks resume
      rejected → approver explicitly denied (Phase 5.5: not yet wired)
    """

    __tablename__ = "override_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    goal_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    intervention_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    package_name: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    approver_label: Mapped[str] = mapped_column(String(64), default="approver", nullable=False)
    sms_status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )  # pending | sent | failed | log_only
    sms_detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", nullable=False, index=True
    )  # pending | approved | expired | rejected
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)


class Preference(Base):
    """Tiny key/value store for runtime-mutable user preferences that don't
    fit into PERSONA.md / MEMORY.md (and shouldn't require a restart):

      - user_name        — display name (overrides $BUDDY_USER_NAME)
      - persona_name     — persona's chosen name (overrides $BUDDY_PERSONA_NAME)
      - timezone         — IANA tz (overrides $BUDDY_TIMEZONE)
      - onboarding_completed_at — ISO timestamp
    """

    __tablename__ = "preferences"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
