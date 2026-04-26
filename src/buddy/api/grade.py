"""Day grade + streak + weekly review endpoints."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from buddy.auth import require_auth
from buddy.db import get_session_factory
from buddy.llm.client import chat
from buddy.llm.models import ModelTier, resolve_model
from buddy.llm.prompts.planning import WEEKLY_REVIEW_SYSTEM
from buddy.memory.store import MemoryStore
from buddy.models import ApiUsage, DayGrade, JournalEntry
from buddy.schemas_phase2 import (
    DayGradeFinalize,
    DayGradeOut,
    GoalPaceSummary,
    PerGoalGrade,
    StreakDay,
    StreakResponse,
    WeeklyReviewBucket,
    WeeklyReviewResponse,
)
from buddy.services.grading import (
    compute_day_grade,
    compute_streak,
    upsert_day_grade,
)

router = APIRouter()


def _to_out(dg: DayGrade) -> DayGradeOut:
    per_goal_payload = dg.per_goal_scores or {}
    per_goal_list = [
        PerGoalGrade(
            goal_id=int(gid),
            statement=info.get("statement", ""),
            pace_target_amount=float(info.get("pace_target_amount") or 0.0),
            pace_target_unit=info.get("pace_target_unit", ""),
            progress_today=float(info.get("progress_today") or 0.0),
            score=float(info.get("score") or 0.0),
        )
        for gid, info in per_goal_payload.items()
    ]
    return DayGradeOut(
        grade_date=dg.grade_date,
        system_score=dg.system_score,
        user_score=dg.user_score,
        per_goal=per_goal_list,
        explanation=dg.explanation,
        user_notes=dg.user_notes,
        is_zero_day=dg.is_zero_day,
        finalized=dg.finalized_at is not None,
        computed_at=dg.computed_at,
    )


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    return cleaned


@router.get(
    "/grade/today", response_model=DayGradeOut, dependencies=[Depends(require_auth)]
)
async def get_today_grade() -> DayGradeOut:
    today = datetime.utcnow().date()
    factory = get_session_factory()
    async with factory() as db:
        result = await compute_day_grade(db, today)
        row = await upsert_day_grade(db, result)
        await db.commit()
        # Re-fetch so the row reflects committed state.
        await db.refresh(row)
    return _to_out(row)


@router.get(
    "/grade/{day}", response_model=DayGradeOut, dependencies=[Depends(require_auth)]
)
async def get_grade(day: date) -> DayGradeOut:
    factory = get_session_factory()
    async with factory() as db:
        row = await db.get(DayGrade, day)
        if row is None:
            # Compute on the fly even for past days that haven't been finalized.
            result = await compute_day_grade(db, day)
            row = await upsert_day_grade(db, result)
            await db.commit()
            await db.refresh(row)
    return _to_out(row)


@router.post(
    "/grade/{day}/finalize",
    response_model=DayGradeOut,
    dependencies=[Depends(require_auth)],
)
async def finalize_grade(day: date, req: DayGradeFinalize) -> DayGradeOut:
    factory = get_session_factory()
    async with factory() as db:
        row = await db.get(DayGrade, day)
        if row is None:
            result = await compute_day_grade(db, day)
            row = await upsert_day_grade(db, result)
        if req.accept_system_score:
            row.user_score = row.system_score
        if req.user_score is not None and not req.accept_system_score:
            row.user_score = req.user_score
        if req.user_notes:
            row.user_notes = req.user_notes
        row.finalized_at = datetime.utcnow()
        await db.commit()
        await db.refresh(row)
    return _to_out(row)


@router.get(
    "/streak", response_model=StreakResponse, dependencies=[Depends(require_auth)]
)
async def get_streak(days: int = 30) -> StreakResponse:
    factory = get_session_factory()
    async with factory() as db:
        streak = await compute_streak(db, days=days)
    return StreakResponse(
        current_streak_length=streak.current_streak_length,
        pause_days=streak.pause_days,
        last_zero_day=streak.last_zero_day,
        history=[
            StreakDay(date=d.day, score=d.score, is_zero=d.is_zero, is_pause=d.is_pause)
            for d in streak.history
        ],
    )


# --- Weekly review --------------------------------------------------------


@router.get(
    "/weekly-review",
    response_model=WeeklyReviewResponse,
    dependencies=[Depends(require_auth)],
)
async def weekly_review(week_offset: int = 0) -> WeeklyReviewResponse:
    """Return a weekly rollup for the calendar week containing today minus
    `week_offset` weeks. Default: this week (Mon-Sun)."""
    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday()) - timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)

    factory = get_session_factory()
    async with factory() as db:
        rows = (
            await db.execute(
                select(DayGrade)
                .where(DayGrade.grade_date >= monday, DayGrade.grade_date <= sunday)
                .order_by(DayGrade.grade_date.asc())
            )
        ).scalars().all()
        journal_rows = (
            await db.execute(
                select(JournalEntry)
                .where(
                    JournalEntry.entry_date >= monday,
                    JournalEntry.entry_date <= sunday,
                )
                .order_by(JournalEntry.entry_date.asc())
            )
        ).scalars().all()

    days_payload = [
        {
            "date": r.grade_date.isoformat(),
            "system_score": r.system_score,
            "user_score": r.user_score,
            "is_zero_day": r.is_zero_day,
            "per_goal": r.per_goal_scores,
        }
        for r in rows
    ]
    journal_payload = [
        {
            "date": j.entry_date.isoformat(),
            "content": j.content,
            "mood": j.mood,
        }
        for j in journal_rows
        if j.content.strip()
    ]

    if not days_payload:
        return WeeklyReviewResponse(
            week_start=monday,
            week_end=sunday,
            average_day_grade=0.0,
            distribution=[],
            per_goal=[],
            pattern_observations=["No grade data for this week yet."],
            journal_excerpts=[j["content"][:160] for j in journal_payload],
            suggested_adjustments=[],
        )

    persona_md = ""
    try:
        store = MemoryStore()
        if store.exists("PERSONA.md"):
            persona_md = store.read("PERSONA.md")
    except Exception:
        persona_md = ""

    user_msg = json.dumps(
        {
            "week_start": monday.isoformat(),
            "week_end": sunday.isoformat(),
            "persona": persona_md,
            "days": days_payload,
            "journal": journal_payload,
        },
        indent=2,
    )
    model = resolve_model(ModelTier.REASONING)
    try:
        result = await chat(
            model=model,
            system=WEEKLY_REVIEW_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=2048,
            temperature=0.4,
        )
    except Exception as exc:
        raise HTTPException(502, f"Weekly review failed: {exc}") from exc

    try:
        payload = json.loads(_strip_fences(result.text))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            502, f"Weekly review JSON parse failed: {result.text[:500]!r}"
        ) from exc

    factory = get_session_factory()
    async with factory() as db:
        db.add(
            ApiUsage(
                provider="anthropic",
                model=result.model,
                operation="weekly_review",
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=result.cost_usd,
            )
        )
        await db.commit()

    distribution = [
        WeeklyReviewBucket(label=str(b.get("label", "?")), count=int(b.get("count", 0)))
        for b in (payload.get("distribution") or [])
    ]
    per_goal = [
        GoalPaceSummary(
            goal_id=int(g.get("goal_id") or 0),
            statement=str(g.get("statement") or ""),
            average_pace=float(g.get("average_pace") or 0.0),
            days_active=int(g.get("days_active") or 0),
            days_zero=int(g.get("days_zero") or 0),
        )
        for g in (payload.get("per_goal") or [])
    ]

    return WeeklyReviewResponse(
        week_start=monday,
        week_end=sunday,
        average_day_grade=float(payload.get("average_day_grade") or 0.0),
        distribution=distribution,
        per_goal=per_goal,
        pattern_observations=list(payload.get("pattern_observations") or []),
        journal_excerpts=list(payload.get("journal_excerpts") or []),
        suggested_adjustments=list(payload.get("suggested_adjustments") or []),
        raw_response=result.text,
    )
