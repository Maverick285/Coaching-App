"""Par-1 grading + streak-as-pause logic.

Per the spec (§7):

    - Each goal has a stated daily pace target.
    - Per-goal grade = clamp(progress_today / pace_target, 0, ∞)
    - Day grade = priority-weighted average of *active* goals' grades.
    - "Zero day" = every active goal scored exactly 0.
    - Streak metric = consecutive non-zero days; missed days *pause* rather
      than reset.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from buddy.models import DayGrade, Goal, ProgressLog


@dataclass
class PerGoal:
    goal_id: int
    statement: str
    pace_target_amount: float
    pace_target_unit: str
    progress_today: float
    score: float


@dataclass
class GradeResult:
    grade_date: date
    system_score: float
    per_goal: list[PerGoal]
    is_zero_day: bool
    explanation: str


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day)
    return start, start + timedelta(days=1)


async def progress_for_goal(
    session: AsyncSession,
    goal_id: int,
    day: date,
) -> float:
    start, end = _day_bounds(day)
    rows = await session.execute(
        select(ProgressLog.attributed_units).where(
            ProgressLog.goal_id == goal_id,
            ProgressLog.recorded_at >= start,
            ProgressLog.recorded_at < end,
        )
    )
    return sum(float(r) for r in rows.scalars().all())


async def active_goals(session: AsyncSession) -> list[Goal]:
    rows = await session.execute(
        select(Goal).where(Goal.state == "active").order_by(Goal.priority.desc(), Goal.id)
    )
    return list(rows.scalars().all())


def _per_goal_score(progress: float, pace_target: float) -> float:
    if pace_target <= 0:
        # No pace set — treat any positive progress as 1.0, otherwise 0.
        return 1.0 if progress > 0 else 0.0
    return max(0.0, progress / pace_target)


def _priority_weighted_avg(per_goal: Iterable[tuple[float, int]]) -> float:
    total_weight = 0.0
    total_score = 0.0
    for score, priority in per_goal:
        # priority 1..5 → weight 1..5
        w = float(priority)
        total_weight += w
        total_score += score * w
    if total_weight == 0.0:
        return 0.0
    return total_score / total_weight


async def compute_day_grade(session: AsyncSession, day: date) -> GradeResult:
    goals = await active_goals(session)
    per_goal: list[PerGoal] = []
    weighted_inputs: list[tuple[float, int]] = []

    for goal in goals:
        progress = await progress_for_goal(session, goal.id, day)
        score = _per_goal_score(progress, goal.pace_target_amount)
        per_goal.append(
            PerGoal(
                goal_id=goal.id,
                statement=goal.statement,
                pace_target_amount=goal.pace_target_amount,
                pace_target_unit=goal.pace_target_unit,
                progress_today=progress,
                score=score,
            )
        )
        weighted_inputs.append((score, goal.priority))

    system_score = _priority_weighted_avg(weighted_inputs) if per_goal else 0.0
    is_zero_day = bool(per_goal) and all(p.score == 0 for p in per_goal)

    explanation = _build_explanation(day, per_goal, system_score, is_zero_day)

    return GradeResult(
        grade_date=day,
        system_score=round(system_score, 3),
        per_goal=per_goal,
        is_zero_day=is_zero_day,
        explanation=explanation,
    )


def _build_explanation(
    day: date, per_goal: list[PerGoal], score: float, zero: bool
) -> str:
    if not per_goal:
        return "No active goals — no grade computed."
    if zero:
        return f"Zero day: every active goal scored 0 on {day.isoformat()}."

    parts: list[str] = [f"Scoring {score:.2f} for {day.isoformat()}."]
    above = [p for p in per_goal if p.score >= 1.0]
    below = [p for p in per_goal if p.score < 1.0 and p.score > 0]
    zero_today = [p for p in per_goal if p.score == 0]

    if above:
        names = ", ".join(f"{p.statement.strip()[:60]} ({p.score:.2f})" for p in above)
        parts.append(f"On or above pace: {names}.")
    if below:
        names = ", ".join(f"{p.statement.strip()[:60]} ({p.score:.2f})" for p in below)
        parts.append(f"Below pace: {names}.")
    if zero_today:
        names = ", ".join(p.statement.strip()[:60] for p in zero_today)
        parts.append(f"No progress today on: {names}.")
    return " ".join(parts)


async def upsert_day_grade(session: AsyncSession, result: GradeResult) -> DayGrade:
    existing = await session.get(DayGrade, result.grade_date)
    per_goal_payload = {
        str(p.goal_id): {
            "statement": p.statement,
            "pace_target_amount": p.pace_target_amount,
            "pace_target_unit": p.pace_target_unit,
            "progress_today": p.progress_today,
            "score": p.score,
        }
        for p in result.per_goal
    }
    if existing is None:
        existing = DayGrade(
            grade_date=result.grade_date,
            system_score=result.system_score,
            per_goal_scores=per_goal_payload,
            explanation=result.explanation,
            is_zero_day=result.is_zero_day,
            computed_at=datetime.utcnow(),
        )
        session.add(existing)
    else:
        # Don't overwrite a finalized grade silently.
        if existing.finalized_at is None:
            existing.system_score = result.system_score
            existing.per_goal_scores = per_goal_payload
            existing.explanation = result.explanation
            existing.is_zero_day = result.is_zero_day
            existing.computed_at = datetime.utcnow()
    return existing


# --- Streak (no-zero-day, with pauses) -------------------------------------


@dataclass
class StreakDay:
    day: date
    score: float
    is_zero: bool
    is_pause: bool


@dataclass
class Streak:
    current_streak_length: int
    pause_days: list[date]
    last_zero_day: date | None
    history: list[StreakDay]


async def compute_streak(session: AsyncSession, days: int = 30) -> Streak:
    """Walk the last `days` of DayGrade rows, treating absent days as pauses."""
    today = datetime.utcnow().date()
    start = today - timedelta(days=days - 1)

    rows = await session.execute(
        select(DayGrade)
        .where(DayGrade.grade_date >= start, DayGrade.grade_date <= today)
        .order_by(DayGrade.grade_date.asc())
    )
    by_date: dict[date, DayGrade] = {dg.grade_date: dg for dg in rows.scalars().all()}

    history: list[StreakDay] = []
    pause_days: list[date] = []
    last_zero_day: date | None = None
    streak_len = 0

    for offset in range(days):
        day = start + timedelta(days=offset)
        row = by_date.get(day)
        if row is None:
            history.append(StreakDay(day, 0.0, False, True))
            pause_days.append(day)
            continue
        score = row.user_score if row.user_score is not None else row.system_score
        is_zero = bool(row.is_zero_day) or (score == 0)
        history.append(StreakDay(day, float(score), is_zero, False))
        if is_zero:
            last_zero_day = day

    # Walk backwards from today to count current streak (skipping pauses).
    for sd in reversed(history):
        if sd.is_pause:
            continue
        if sd.is_zero:
            break
        streak_len += 1

    return Streak(
        current_streak_length=streak_len,
        pause_days=pause_days,
        last_zero_day=last_zero_day,
        history=history,
    )
