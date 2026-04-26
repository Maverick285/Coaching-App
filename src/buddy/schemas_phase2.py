"""Pydantic request/response schemas for the Phase 2 surface (goals, tasks,
journal, par-1 grading, weekly review).

Kept in a separate module from `schemas.py` so the Phase 0 surface stays small.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# --- Enums (string-typed for API ergonomics) -------------------------------

GoalState = Literal["proposed", "active", "paused", "completed", "abandoned"]
GoalApproach = Literal["user_driven", "system_assisted", "hybrid"]
GoalPlanSource = Literal["user_plan", "system_plan", "no_plan"]
GoalTimeframe = Literal["open_ended", "deadline", "recurring"]
TaskState = Literal["proposed", "scheduled", "in_progress", "done", "skipped"]
IntentionCueType = Literal["time_place", "routine", "event", "obstacle"]
ProgressSource = Literal["manual", "voice", "pc_agent", "usage_stats", "system"]


# --- Goals -----------------------------------------------------------------


class GoalCreate(BaseModel):
    statement: str = Field(min_length=1, max_length=2000)
    timeframe: GoalTimeframe = "open_ended"
    deadline: date | None = None
    priority: int = Field(default=3, ge=1, le=5)
    approach: GoalApproach = "user_driven"
    plan_source: GoalPlanSource = "user_plan"
    intervention_ceiling: int = Field(default=2, ge=0, le=5)
    pace_target_unit: str = ""
    pace_target_amount: float = 0.0
    pace_target_description: str = ""
    mvp_threshold: str = ""
    parent_goal_id: int | None = None


class GoalUpdate(BaseModel):
    statement: str | None = None
    timeframe: GoalTimeframe | None = None
    deadline: date | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    approach: GoalApproach | None = None
    plan_source: GoalPlanSource | None = None
    state: GoalState | None = None
    intervention_ceiling: int | None = Field(default=None, ge=0, le=5)
    pace_target_unit: str | None = None
    pace_target_amount: float | None = None
    pace_target_description: str | None = None
    mvp_threshold: str | None = None
    reflection_log: str | None = None


class GoalOut(BaseModel):
    id: int
    statement: str
    timeframe: GoalTimeframe
    deadline: date | None
    priority: int
    approach: GoalApproach
    plan_source: GoalPlanSource
    state: GoalState
    intervention_ceiling: int
    pace_target_unit: str
    pace_target_amount: float
    pace_target_description: str
    mvp_threshold: str
    parent_goal_id: int | None
    reflection_log: str
    created_at: datetime
    updated_at: datetime


class GoalsListResponse(BaseModel):
    goals: list[GoalOut]


class GoalDetail(BaseModel):
    goal: GoalOut
    tasks: list["TaskOut"]
    intentions: list["IntentionOut"]
    today_progress: float = 0.0
    today_grade: float = 0.0


# --- Tasks -----------------------------------------------------------------


class TaskCreate(BaseModel):
    goal_id: int
    description: str = Field(min_length=1, max_length=2000)
    definition_of_done: str = ""
    estimated_duration_minutes: int | None = None
    scheduled_at: datetime | None = None
    triggering_intention_id: int | None = None
    first_60_seconds: str = ""


class TaskUpdate(BaseModel):
    description: str | None = None
    definition_of_done: str | None = None
    estimated_duration_minutes: int | None = None
    actual_duration_minutes: int | None = None
    scheduled_at: datetime | None = None
    state: TaskState | None = None
    first_60_seconds: str | None = None


class TaskOut(BaseModel):
    id: int
    goal_id: int
    description: str
    definition_of_done: str
    estimated_duration_minutes: int | None
    actual_duration_minutes: int | None
    scheduled_at: datetime | None
    triggering_intention_id: int | None
    state: TaskState
    first_60_seconds: str
    created_at: datetime
    completed_at: datetime | None


class TasksListResponse(BaseModel):
    tasks: list[TaskOut]


# --- Implementation intentions --------------------------------------------


class IntentionCreate(BaseModel):
    goal_id: int | None = None
    task_id: int | None = None
    cue_type: IntentionCueType
    cue_text: str
    response_text: str


class IntentionOut(BaseModel):
    id: int
    goal_id: int | None
    task_id: int | None
    cue_type: IntentionCueType
    cue_text: str
    response_text: str
    is_active: bool
    created_at: datetime


# --- WOOP ------------------------------------------------------------------


class WoopRequest(BaseModel):
    wish: str = Field(min_length=1)
    initial_obstacle: str | None = None
    desired_pace_unit: str | None = None  # e.g. "pages", "sessions"


class WoopResponse(BaseModel):
    wish: str
    outcome: str
    obstacles: list[str]
    plan: list[str]  # if-then statements
    suggested_intentions: list[IntentionCreate]
    suggested_tasks: list[str]
    suggested_pace_unit: str
    suggested_pace_amount: float
    suggested_pace_description: str
    raw_response: str = ""


# --- Progress logging ------------------------------------------------------


class ProgressLogCreate(BaseModel):
    """Direct, structured progress log."""

    goal_id: int
    raw_text: str = ""
    attributed_units: float = 0.0
    unit_label: str = ""
    source: ProgressSource = "manual"
    note: str = ""


class ProgressLogOut(BaseModel):
    id: int
    goal_id: int
    recorded_at: datetime
    raw_text: str
    attributed_units: float
    unit_label: str
    source: ProgressSource
    confidence: float
    note: str


class ProgressFreeForm(BaseModel):
    """Free-form progress capture; the fast LLM attributes to a goal."""

    text: str = Field(min_length=1, max_length=4000)
    source: ProgressSource = "manual"


class AttributedProgress(BaseModel):
    goal_id: int
    units: float
    unit_label: str
    confidence: float
    rationale: str


class ProgressFreeFormResponse(BaseModel):
    attributions: list[AttributedProgress]
    logged: list[ProgressLogOut]
    unattributed_text: str = ""


# --- Day grade -------------------------------------------------------------


class PerGoalGrade(BaseModel):
    goal_id: int
    statement: str
    pace_target_amount: float
    pace_target_unit: str
    progress_today: float
    score: float


class DayGradeOut(BaseModel):
    grade_date: date
    system_score: float
    user_score: float | None
    per_goal: list[PerGoalGrade]
    explanation: str
    user_notes: str
    is_zero_day: bool
    finalized: bool
    computed_at: datetime


class DayGradeFinalize(BaseModel):
    user_score: float | None = Field(default=None, ge=0.0)
    user_notes: str = ""
    accept_system_score: bool = True


# --- Streak ---------------------------------------------------------------


class StreakDay(BaseModel):
    date: date
    score: float
    is_zero: bool
    is_pause: bool


class StreakResponse(BaseModel):
    current_streak_length: int  # consecutive non-zero days, ignoring pauses
    pause_days: list[date]
    last_zero_day: date | None
    history: list[StreakDay]


# --- Weekly review --------------------------------------------------------


class WeeklyReviewBucket(BaseModel):
    label: str
    count: int


class GoalPaceSummary(BaseModel):
    goal_id: int
    statement: str
    average_pace: float
    days_active: int
    days_zero: int


class WeeklyReviewResponse(BaseModel):
    week_start: date
    week_end: date
    average_day_grade: float
    distribution: list[WeeklyReviewBucket]
    per_goal: list[GoalPaceSummary]
    pattern_observations: list[str]
    journal_excerpts: list[str]
    suggested_adjustments: list[str]
    raw_response: str = ""


# --- Journal --------------------------------------------------------------


class JournalEntryWrite(BaseModel):
    content: str = ""
    mood: str = ""
    tags: list[str] = []


class JournalEntryOut(BaseModel):
    entry_date: date
    content: str
    mood: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class JournalListResponse(BaseModel):
    entries: list[JournalEntryOut]


# Forward-ref resolution for GoalDetail.
GoalDetail.model_rebuild()
