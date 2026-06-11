"""Goals + tasks + implementation intentions + WOOP planning endpoints."""

from __future__ import annotations

import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from buddy.auth import require_auth
from buddy.config import get_settings
from buddy.db import get_session_factory
from buddy.llm.client import chat, chat_with_tool
from buddy.llm.models import ModelTier, resolve_model
from buddy.llm.prompts.planning import (
    WOOP_SYSTEM,
    build_woop_user_message,
)
from buddy.llm.tools import PROPOSE_WOOP_PLAN_TOOL
from buddy.models import (
    ApiUsage,
    Goal,
    ImplementationIntention,
    Task,
)
from buddy.schemas_phase2 import (
    GoalCreate,
    GoalDetail,
    GoalOut,
    GoalsListResponse,
    GoalUpdate,
    IntentionCreate,
    IntentionOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    TasksListResponse,
    WoopRequest,
    WoopResponse,
)
from buddy.services.grading import progress_for_goal

router = APIRouter()


def _goal_to_out(g: Goal) -> GoalOut:
    return GoalOut.model_validate(
        {
            "id": g.id,
            "statement": g.statement,
            "timeframe": g.timeframe,
            "deadline": g.deadline,
            "priority": g.priority,
            "approach": g.approach,
            "plan_source": g.plan_source,
            "state": g.state,
            "intervention_ceiling": g.intervention_ceiling,
            "pace_target_unit": g.pace_target_unit,
            "pace_target_amount": g.pace_target_amount,
            "pace_target_description": g.pace_target_description,
            "mvp_threshold": g.mvp_threshold,
            "parent_goal_id": g.parent_goal_id,
            "reflection_log": g.reflection_log,
            "stake_webhook_url": g.stake_webhook_url,
            "stake_webhook_secret": g.stake_webhook_secret,
            "stake_active": g.stake_active,
            "created_at": g.created_at,
            "updated_at": g.updated_at,
        }
    )


def _task_to_out(t: Task) -> TaskOut:
    return TaskOut.model_validate(
        {
            "id": t.id,
            "goal_id": t.goal_id,
            "description": t.description,
            "definition_of_done": t.definition_of_done,
            "estimated_duration_minutes": t.estimated_duration_minutes,
            "actual_duration_minutes": t.actual_duration_minutes,
            "scheduled_at": t.scheduled_at,
            "triggering_intention_id": t.triggering_intention_id,
            "state": t.state,
            "first_60_seconds": t.first_60_seconds,
            "created_at": t.created_at,
            "completed_at": t.completed_at,
        }
    )


def _intention_to_out(i: ImplementationIntention) -> IntentionOut:
    return IntentionOut.model_validate(
        {
            "id": i.id,
            "goal_id": i.goal_id,
            "task_id": i.task_id,
            "cue_type": i.cue_type,
            "cue_text": i.cue_text,
            "response_text": i.response_text,
            "is_active": i.is_active,
            "created_at": i.created_at,
        }
    )


# --- Goals -----------------------------------------------------------------


@router.get("/goals", response_model=GoalsListResponse, dependencies=[Depends(require_auth)])
async def list_goals(state: str | None = None) -> GoalsListResponse:
    factory = get_session_factory()
    async with factory() as db:
        q = select(Goal).order_by(Goal.priority.desc(), Goal.id.desc())
        if state:
            q = q.where(Goal.state == state)
        rows = (await db.execute(q)).scalars().all()
    return GoalsListResponse(goals=[_goal_to_out(g) for g in rows])


ACTIVE_GOAL_LIMIT = 4  # spec §20.1


async def _enforce_active_limit(db, parent_goal_id: int | None) -> None:
    """Per master spec §20.1, the user keeps 2-4 active goals at the
    top level. Sub-goals (those with a parent) don't count toward the
    cap; they're internal structure. Returns None on success, raises
    HTTPException 409 with a code the client can switch on otherwise.
    """
    if parent_goal_id is not None:
        return
    count = (
        await db.execute(
            select(Goal).where(Goal.state == "active", Goal.parent_goal_id.is_(None))
        )
    ).scalars().all()
    if len(count) >= ACTIVE_GOAL_LIMIT:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "active_goal_limit",
                "message": (
                    f"You already have {len(count)} active top-level "
                    f"goals. Pause one to add another, or save this as a "
                    f"backlog item."
                ),
                "limit": ACTIVE_GOAL_LIMIT,
            },
        )


@router.post("/goals", response_model=GoalOut, dependencies=[Depends(require_auth)])
async def create_goal(req: GoalCreate) -> GoalOut:
    factory = get_session_factory()
    async with factory() as db:
        # Cap only applies to *active* top-level goals. Stashing a goal
        # directly into the backlog (state=paused) is always allowed.
        if req.state == "active":
            await _enforce_active_limit(db, req.parent_goal_id)
        goal = Goal(
            statement=req.statement,
            timeframe=req.timeframe,
            deadline=req.deadline,
            priority=req.priority,
            approach=req.approach,
            plan_source=req.plan_source,
            state=req.state,
            intervention_ceiling=req.intervention_ceiling,
            pace_target_unit=req.pace_target_unit,
            pace_target_amount=req.pace_target_amount,
            pace_target_description=req.pace_target_description,
            mvp_threshold=req.mvp_threshold,
            parent_goal_id=req.parent_goal_id,
            stake_webhook_url=req.stake_webhook_url,
            stake_webhook_secret=req.stake_webhook_secret,
            stake_active=req.stake_active,
        )
        db.add(goal)
        await db.commit()
        await db.refresh(goal)
    return _goal_to_out(goal)


@router.get("/goals/{goal_id}", response_model=GoalDetail, dependencies=[Depends(require_auth)])
async def get_goal(goal_id: int) -> GoalDetail:
    factory = get_session_factory()
    async with factory() as db:
        goal = await db.get(Goal, goal_id)
        if goal is None:
            raise HTTPException(404, "Goal not found.")
        tasks = (
            await db.execute(
                select(Task).where(Task.goal_id == goal_id).order_by(Task.id.desc())
            )
        ).scalars().all()
        intentions = (
            await db.execute(
                select(ImplementationIntention)
                .where(ImplementationIntention.goal_id == goal_id)
                .order_by(ImplementationIntention.id.desc())
            )
        ).scalars().all()
        today = datetime.utcnow().date()
        progress = await progress_for_goal(db, goal_id, today)
        score = (
            progress / goal.pace_target_amount
            if goal.pace_target_amount > 0
            else (1.0 if progress > 0 else 0.0)
        )

    return GoalDetail(
        goal=_goal_to_out(goal),
        tasks=[_task_to_out(t) for t in tasks],
        intentions=[_intention_to_out(i) for i in intentions],
        today_progress=progress,
        today_grade=round(score, 3),
    )


@router.patch("/goals/{goal_id}", response_model=GoalOut, dependencies=[Depends(require_auth)])
async def update_goal(goal_id: int, req: GoalUpdate) -> GoalOut:
    factory = get_session_factory()
    updates = req.model_dump(exclude_unset=True)
    async with factory() as db:
        goal = await db.get(Goal, goal_id)
        if goal is None:
            raise HTTPException(404, "Goal not found.")
        # If we're flipping a top-level goal back to "active", make sure
        # the cap still holds. Pausing/abandoning is always fine.
        new_state = updates.get("state")
        if (
            new_state == "active"
            and goal.state != "active"
            and goal.parent_goal_id is None
        ):
            await _enforce_active_limit(db, parent_goal_id=None)
        for field, value in updates.items():
            setattr(goal, field, value)
        goal.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(goal)
    return _goal_to_out(goal)


@router.delete("/goals/{goal_id}", dependencies=[Depends(require_auth)])
async def delete_goal(goal_id: int) -> dict:
    factory = get_session_factory()
    async with factory() as db:
        goal = await db.get(Goal, goal_id)
        if goal is None:
            raise HTTPException(404, "Goal not found.")
        await db.delete(goal)
        await db.commit()
    return {"deleted": goal_id}


# --- Tasks -----------------------------------------------------------------


@router.get("/tasks", response_model=TasksListResponse, dependencies=[Depends(require_auth)])
async def list_tasks(
    goal_id: int | None = None, state: str | None = None
) -> TasksListResponse:
    factory = get_session_factory()
    async with factory() as db:
        q = select(Task).order_by(Task.scheduled_at.is_(None), Task.scheduled_at, Task.id.desc())
        if goal_id is not None:
            q = q.where(Task.goal_id == goal_id)
        if state:
            q = q.where(Task.state == state)
        rows = (await db.execute(q)).scalars().all()
    return TasksListResponse(tasks=[_task_to_out(t) for t in rows])


@router.post("/tasks", response_model=TaskOut, dependencies=[Depends(require_auth)])
async def create_task(req: TaskCreate) -> TaskOut:
    factory = get_session_factory()
    async with factory() as db:
        # Verify the goal exists.
        goal = await db.get(Goal, req.goal_id)
        if goal is None:
            raise HTTPException(404, f"Parent goal {req.goal_id} not found.")
        task = Task(
            goal_id=req.goal_id,
            description=req.description,
            definition_of_done=req.definition_of_done,
            estimated_duration_minutes=req.estimated_duration_minutes,
            scheduled_at=req.scheduled_at,
            triggering_intention_id=req.triggering_intention_id,
            first_60_seconds=req.first_60_seconds,
            state="scheduled" if req.scheduled_at else "proposed",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
    return _task_to_out(task)


@router.patch("/tasks/{task_id}", response_model=TaskOut, dependencies=[Depends(require_auth)])
async def update_task(task_id: int, req: TaskUpdate) -> TaskOut:
    factory = get_session_factory()
    async with factory() as db:
        task = await db.get(Task, task_id)
        if task is None:
            raise HTTPException(404, "Task not found.")
        updates = req.model_dump(exclude_unset=True)
        new_state = updates.get("state")
        for field, value in updates.items():
            setattr(task, field, value)
        if new_state == "done" and task.completed_at is None:
            task.completed_at = datetime.utcnow()
        if new_state and new_state != "done":
            task.completed_at = None
        await db.commit()
        await db.refresh(task)
    return _task_to_out(task)


@router.delete("/tasks/{task_id}", dependencies=[Depends(require_auth)])
async def delete_task(task_id: int) -> dict:
    factory = get_session_factory()
    async with factory() as db:
        task = await db.get(Task, task_id)
        if task is None:
            raise HTTPException(404, "Task not found.")
        await db.delete(task)
        await db.commit()
    return {"deleted": task_id}


# --- Implementation intentions --------------------------------------------


@router.post(
    "/intentions", response_model=IntentionOut, dependencies=[Depends(require_auth)]
)
async def create_intention(req: IntentionCreate) -> IntentionOut:
    if req.goal_id is None and req.task_id is None:
        raise HTTPException(400, "Provide goal_id or task_id.")
    factory = get_session_factory()
    async with factory() as db:
        if req.goal_id is not None and (await db.get(Goal, req.goal_id)) is None:
            raise HTTPException(404, f"Goal {req.goal_id} not found.")
        if req.task_id is not None and (await db.get(Task, req.task_id)) is None:
            raise HTTPException(404, f"Task {req.task_id} not found.")
        intention = ImplementationIntention(
            goal_id=req.goal_id,
            task_id=req.task_id,
            cue_type=req.cue_type,
            cue_text=req.cue_text,
            response_text=req.response_text,
        )
        db.add(intention)
        await db.commit()
        await db.refresh(intention)
    return _intention_to_out(intention)


@router.delete("/intentions/{intention_id}", dependencies=[Depends(require_auth)])
async def delete_intention(intention_id: int) -> dict:
    factory = get_session_factory()
    async with factory() as db:
        intention = await db.get(ImplementationIntention, intention_id)
        if intention is None:
            raise HTTPException(404, "Intention not found.")
        await db.delete(intention)
        await db.commit()
    return {"deleted": intention_id}


# --- WOOP -----------------------------------------------------------------


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    return cleaned


@router.post("/goals/woop", response_model=WoopResponse, dependencies=[Depends(require_auth)])
async def run_woop(req: WoopRequest) -> WoopResponse:
    """Run WOOP synthesis on a wish; return a structured plan the caller
    can review. Uses Anthropic native tool-use for reliable structured
    output (no regex JSON parsing)."""
    settings = get_settings()
    model = resolve_model(ModelTier.REASONING)
    user_msg = build_woop_user_message(
        wish=req.wish,
        initial_obstacle=req.initial_obstacle,
        desired_pace_unit=req.desired_pace_unit,
        user_name=settings.user_name,
    )
    last_error = ""
    payload: dict | None = None
    result = None
    for attempt in range(2):
        try:
            result = await chat_with_tool(
                model=model,
                system=WOOP_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
                tool=PROPOSE_WOOP_PLAN_TOOL,
                max_tokens=2048,
                temperature=0.4 if attempt == 0 else 0.2,
            )
            payload = result.tool_input
            break
        except Exception as exc:
            last_error = str(exc)
            continue
    if payload is None or result is None:
        raise HTTPException(502, f"WOOP synthesis failed: {last_error}")

    factory = get_session_factory()
    async with factory() as db:
        db.add(
            ApiUsage(
                provider="anthropic",
                model=result.model,
                operation="woop",
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=result.cost_usd,
            )
        )
        await db.commit()

    intentions = [
        IntentionCreate(
            goal_id=None,
            task_id=None,
            cue_type=item.get("cue_type", "obstacle"),
            cue_text=item.get("cue_text", ""),
            response_text=item.get("response_text", ""),
        )
        for item in (payload.get("suggested_intentions") or [])
        if item.get("cue_text") and item.get("response_text")
    ]

    return WoopResponse(
        wish=payload.get("wish", req.wish),
        outcome=payload.get("outcome", ""),
        obstacles=payload.get("obstacles", []) or [],
        plan=payload.get("plan", []) or [],
        suggested_intentions=intentions,
        suggested_tasks=payload.get("suggested_tasks", []) or [],
        suggested_pace_unit=payload.get("suggested_pace_unit", "")
        or req.desired_pace_unit
        or "",
        suggested_pace_amount=float(payload.get("suggested_pace_amount") or 0.0),
        suggested_pace_description=payload.get("suggested_pace_description", ""),
        raw_response=result.text,
    )
