"""POST /goals/plan — wish → full structured plan, then atomic save.

The user states a wish and optional target date. We ask Claude (reasoning
tier) to produce a complete plan covering pace target, no-zero floor,
milestones, first-week tasks, and if-then plans. The client shows it to
the user; on accept, the client calls /goals/plan/apply which creates
the goal + sub-goals + tasks + intentions in one transaction.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from buddy.auth import require_auth
from buddy.config import get_settings
from buddy.db import get_session_factory
from buddy.llm.client import chat_with_tool
from buddy.llm.models import ModelTier, resolve_model
from buddy.llm.prompts.goal_planner import (
    GOAL_PLANNER_SYSTEM,
    build_goal_planner_user_message,
)
from buddy.llm.tools import PROPOSE_GOAL_PLAN_TOOL
from buddy.models import ApiUsage, Goal, ImplementationIntention, Task
from buddy.services.profile import resolve_user_name

router = APIRouter()


class GoalPlanRequest(BaseModel):
    wish: str = Field(min_length=2, max_length=2000)
    deadline: date | None = None


class PlannedMilestone(BaseModel):
    statement: str
    deadline: date | None = None
    pace_target_unit: str = ""
    pace_target_amount: float = 0.0
    mvp_threshold: str = ""


class PlannedTask(BaseModel):
    description: str
    estimated_duration_minutes: int | None = None
    first_60_seconds: str = ""
    scheduled_at: datetime | None = None


class PlannedIntention(BaseModel):
    cue_type: Literal["time_place", "routine", "event", "obstacle"]
    cue_text: str
    response_text: str


class GoalPlan(BaseModel):
    statement: str
    rationale: str = ""
    user_facing_summary: str = ""
    pace_target_unit: str
    pace_target_amount: float
    pace_target_description: str = ""
    mvp_threshold: str = ""
    intervention_ceiling: int = 2
    approach: Literal["user_driven", "hybrid", "system_assisted"] = "hybrid"
    priority: int = 3
    deadline: date | None = None
    milestones: list[PlannedMilestone] = []
    first_week_tasks: list[PlannedTask] = []
    implementation_intentions: list[PlannedIntention] = []
    obstacles: list[str] = []
    outcome_vision: str = ""


class GoalPlanResponse(BaseModel):
    plan: GoalPlan
    raw_response: str


class GoalPlanApplyRequest(BaseModel):
    plan: GoalPlan


class GoalPlanApplyResponse(BaseModel):
    goal_id: int
    milestone_ids: list[int]
    task_ids: list[int]
    intention_ids: list[int]


@router.post(
    "/goals/plan",
    response_model=GoalPlanResponse,
    dependencies=[Depends(require_auth)],
)
async def plan_goal(req: GoalPlanRequest) -> GoalPlanResponse:
    settings = get_settings()
    user_name = await resolve_user_name()
    today = date.today()
    if req.deadline and req.deadline < today:
        raise HTTPException(400, "Deadline can't be in the past.")

    user_msg = build_goal_planner_user_message(
        wish=req.wish.strip(),
        user_name=user_name or settings.user_name,
        today_iso=today.isoformat(),
        deadline_iso=req.deadline.isoformat() if req.deadline else None,
    )
    model = resolve_model(ModelTier.REASONING)

    payload: dict[str, Any] | None = None
    last_error = ""
    result = None
    for attempt in range(2):
        try:
            result = await chat_with_tool(
                model=model,
                system=GOAL_PLANNER_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
                tool=PROPOSE_GOAL_PLAN_TOOL,
                max_tokens=3000,
                temperature=0.4 if attempt == 0 else 0.2,
            )
            payload = dict(result.tool_input)
            break
        except Exception as exc:
            last_error = f"tool call failed: {exc}"
            continue

    if payload is None or result is None:
        raise HTTPException(502, f"Goal planner failed: {last_error}")

    factory = get_session_factory()
    async with factory() as db:
        db.add(
            ApiUsage(
                provider="anthropic",
                model=result.model,
                operation="goal:plan",
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=result.cost_usd,
            )
        )
        await db.commit()

    # Always fold the user-supplied deadline back into the plan, in case
    # the model dropped it.
    if req.deadline:
        payload["deadline"] = req.deadline.isoformat()

    try:
        plan = GoalPlan.model_validate(payload)
    except Exception as exc:
        raise HTTPException(502, f"Plan failed schema validation: {exc}") from exc

    return GoalPlanResponse(plan=plan, raw_response=result.text)


@router.post(
    "/goals/plan/apply",
    response_model=GoalPlanApplyResponse,
    dependencies=[Depends(require_auth)],
)
async def apply_plan(req: GoalPlanApplyRequest) -> GoalPlanApplyResponse:
    """Atomically create the parent goal + milestones + tasks + intentions."""
    from buddy.api.goals import _enforce_active_limit
    plan = req.plan
    factory = get_session_factory()
    async with factory() as db:
        # Same 2-4 active-top-level cap that the bare /goals endpoint
        # enforces — milestones don't count, only the parent.
        await _enforce_active_limit(db, parent_goal_id=None)
        parent = Goal(
            statement=plan.statement,
            timeframe="deadline" if plan.deadline else "open_ended",
            deadline=plan.deadline,
            priority=max(1, min(5, plan.priority)),
            approach=plan.approach,
            plan_source="system_plan",
            state="active",
            intervention_ceiling=max(0, min(4, plan.intervention_ceiling)),
            pace_target_unit=plan.pace_target_unit,
            pace_target_amount=float(plan.pace_target_amount),
            pace_target_description=plan.pace_target_description,
            mvp_threshold=plan.mvp_threshold,
        )
        db.add(parent)
        await db.flush()
        parent_id = parent.id

        milestone_ids: list[int] = []
        for m in plan.milestones:
            sub = Goal(
                statement=m.statement,
                timeframe="deadline" if m.deadline else "open_ended",
                deadline=m.deadline,
                priority=parent.priority,
                approach=plan.approach,
                plan_source="system_plan",
                state="active",
                intervention_ceiling=parent.intervention_ceiling,
                pace_target_unit=m.pace_target_unit,
                pace_target_amount=float(m.pace_target_amount),
                pace_target_description="",
                mvp_threshold=m.mvp_threshold,
                parent_goal_id=parent_id,
            )
            db.add(sub)
            await db.flush()
            milestone_ids.append(sub.id)

        task_ids: list[int] = []
        for t in plan.first_week_tasks:
            task = Task(
                goal_id=parent_id,
                description=t.description,
                definition_of_done="",
                estimated_duration_minutes=t.estimated_duration_minutes,
                scheduled_at=t.scheduled_at,
                first_60_seconds=t.first_60_seconds or "",
                state="scheduled" if t.scheduled_at else "proposed",
            )
            db.add(task)
            await db.flush()
            task_ids.append(task.id)

        intention_ids: list[int] = []
        for i in plan.implementation_intentions:
            intention = ImplementationIntention(
                goal_id=parent_id,
                task_id=None,
                cue_type=i.cue_type,
                cue_text=i.cue_text,
                response_text=i.response_text,
            )
            db.add(intention)
            await db.flush()
            intention_ids.append(intention.id)

        await db.commit()

    return GoalPlanApplyResponse(
        goal_id=parent_id,
        milestone_ids=milestone_ids,
        task_ids=task_ids,
        intention_ids=intention_ids,
    )
