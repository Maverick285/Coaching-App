"""Natural-language batch operations on tasks.

The user types or dictates something like:

    "add a task to draft the spec by 5pm. also delete the gym one and
     mark dishes done."

We send their text + a snapshot of (active goals, open tasks) to an LLM
which returns a strict JSON list of typed operations:

    [
      {"op": "create",   "goal_id": 3, "description": "draft the spec",
       "scheduled_at": "2026-04-27T17:00:00", "estimated_duration_minutes": 90},
      {"op": "complete", "task_id": 12},
      {"op": "delete",   "task_id": 9}
    ]

We apply them in order and return both the parsed ops + their results so
the client can show "added 1, completed 1, deleted 1".
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from buddy.auth import require_auth
from buddy.db import get_session_factory
from buddy.llm.client import chat
from buddy.llm.models import ModelTier, resolve_model
from buddy.models import ApiUsage, Goal, Task
from buddy.services.profile import resolve_timezone

router = APIRouter()


class TaskBatchNLRequest(BaseModel):
    text: str = Field(min_length=1)
    source: Literal["text", "voice"] = "text"


class TaskBatchOpResult(BaseModel):
    op: str
    status: Literal["ok", "error"]
    task_id: int | None = None
    detail: str = ""


class TaskBatchNLResponse(BaseModel):
    parsed_ops: list[dict]
    results: list[TaskBatchOpResult]
    raw_text: str


_SYSTEM = """You translate a user's natural-language task command into a strict JSON
list of operations. The user has goals (with ids) and tasks (with ids,
descriptions, current state). They may want to create, complete, update, or
delete one or several tasks in a single utterance.

Output a JSON object with one key, "operations", whose value is a list of
operation objects. Each operation has an "op" field. Allowed shapes:

  {"op": "create", "goal_id": <int>, "description": <str>,
   "scheduled_at": <iso-datetime or null>,
   "estimated_duration_minutes": <int or null>,
   "first_60_seconds": <str or "">,
   "definition_of_done": <str or "">}

  {"op": "complete", "task_id": <int>}

  {"op": "update", "task_id": <int>,
   "description": <str or null>,
   "scheduled_at": <iso-datetime or null>,
   "estimated_duration_minutes": <int or null>}

  {"op": "delete", "task_id": <int>}

Rules:
- Only emit operations that are clearly requested. If you can't tell, omit.
- Resolve "the gym task", "the spec one", "dishes" by matching against the
  task list; if multiple match, prefer the most recently created.
- For create: pick the most relevant goal_id from the active goals list. If
  none of the goals seem to fit, pick the highest-priority active goal.
- "end", "finish", "done" mean op=complete (not delete).
- "cancel", "scrap", "remove", "delete" mean op=delete.
- Times like "at 5pm", "tomorrow morning" must be resolved against
  the user's local clock — use the provided "now" timestamp as the anchor.
- Output JSON only, no prose, no markdown fences."""


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    return cleaned


def _build_user_message(
    *,
    text: str,
    goals: list[Goal],
    tasks: list[Task],
    tz_name: str,
    now: datetime,
) -> str:
    goal_lines = [
        f"  - id={g.id} priority={g.priority} state={g.state} | {g.statement}"
        for g in goals
    ]
    task_lines = [
        f"  - id={t.id} goal_id={t.goal_id} state={t.state} "
        f"scheduled_at={t.scheduled_at.isoformat() if t.scheduled_at else 'null'} "
        f"| {t.description}"
        for t in tasks
    ]
    return (
        f"now = {now.isoformat()} ({tz_name})\n\n"
        f"active goals:\n" + ("\n".join(goal_lines) or "  (none)") + "\n\n"
        f"current tasks (open + recent):\n" + ("\n".join(task_lines) or "  (none)") + "\n\n"
        f"user said: {text!r}\n"
    )


@router.post(
    "/tasks/batch_nl",
    response_model=TaskBatchNLResponse,
    dependencies=[Depends(require_auth)],
)
async def tasks_batch_nl(req: TaskBatchNLRequest) -> TaskBatchNLResponse:
    factory = get_session_factory()
    async with factory() as db:
        goals = (
            await db.execute(
                select(Goal)
                .where(Goal.state == "active")
                .order_by(Goal.priority.desc(), Goal.id.desc())
            )
        ).scalars().all()
        # Pull open tasks plus a few recently-completed so the model can
        # resolve references like "mark dishes done" against done tasks too.
        tasks = (
            await db.execute(
                select(Task)
                .where(Task.state.in_(("proposed", "scheduled", "in_progress", "done")))
                .order_by(Task.id.desc())
                .limit(50)
            )
        ).scalars().all()

    tz_name = await resolve_timezone()
    user_message = _build_user_message(
        text=req.text,
        goals=list(goals),
        tasks=list(tasks),
        tz_name=tz_name,
        now=datetime.utcnow(),
    )

    model = resolve_model(ModelTier.FAST)
    try:
        result = await chat(
            model=model,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=1200,
            temperature=0.1,
        )
    except Exception as exc:
        raise HTTPException(502, f"NL parse failed: {exc}") from exc

    try:
        parsed = json.loads(_strip_fences(result.text))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            502, f"NL parser returned non-JSON: {result.text[:400]!r}"
        ) from exc

    operations = parsed.get("operations") if isinstance(parsed, dict) else parsed
    if not isinstance(operations, list):
        raise HTTPException(502, "NL parser did not return an operations list.")

    results: list[TaskBatchOpResult] = []
    async with factory() as db:
        for op in operations:
            results.append(await _apply_op(db, op))
        await db.commit()
        db.add(
            ApiUsage(
                provider="anthropic",
                model=result.model,
                operation="tasks:batch_nl",
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=result.cost_usd,
            )
        )
        await db.commit()

    return TaskBatchNLResponse(
        parsed_ops=operations,
        results=results,
        raw_text=result.text,
    )


def _coerce_dt(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


async def _apply_op(db, op: dict) -> TaskBatchOpResult:
    if not isinstance(op, dict):
        return TaskBatchOpResult(op="?", status="error", detail="op was not an object")
    kind = str(op.get("op", "")).lower()

    if kind == "create":
        goal_id = op.get("goal_id")
        description = (op.get("description") or "").strip()
        if not goal_id or not description:
            return TaskBatchOpResult(
                op=kind, status="error", detail="missing goal_id or description"
            )
        goal = await db.get(Goal, int(goal_id))
        if goal is None:
            return TaskBatchOpResult(
                op=kind, status="error", detail=f"goal {goal_id} not found"
            )
        scheduled = _coerce_dt(op.get("scheduled_at"))
        task = Task(
            goal_id=int(goal_id),
            description=description,
            definition_of_done=op.get("definition_of_done") or "",
            estimated_duration_minutes=op.get("estimated_duration_minutes"),
            scheduled_at=scheduled,
            first_60_seconds=op.get("first_60_seconds") or "",
            state="scheduled" if scheduled else "proposed",
        )
        db.add(task)
        await db.flush()
        return TaskBatchOpResult(op=kind, status="ok", task_id=task.id)

    if kind in ("complete", "done", "finish"):
        task_id = op.get("task_id")
        task = await db.get(Task, int(task_id)) if task_id else None
        if task is None:
            return TaskBatchOpResult(op=kind, status="error", detail="task not found")
        task.state = "done"
        task.completed_at = datetime.utcnow()
        return TaskBatchOpResult(op="complete", status="ok", task_id=task.id)

    if kind == "update":
        task_id = op.get("task_id")
        task = await db.get(Task, int(task_id)) if task_id else None
        if task is None:
            return TaskBatchOpResult(op=kind, status="error", detail="task not found")
        if op.get("description"):
            task.description = str(op["description"]).strip()
        if "scheduled_at" in op:
            task.scheduled_at = _coerce_dt(op.get("scheduled_at"))
        if op.get("estimated_duration_minutes") is not None:
            try:
                task.estimated_duration_minutes = int(op["estimated_duration_minutes"])
            except (TypeError, ValueError):
                pass
        return TaskBatchOpResult(op=kind, status="ok", task_id=task.id)

    if kind in ("delete", "remove", "cancel", "scrap"):
        task_id = op.get("task_id")
        task = await db.get(Task, int(task_id)) if task_id else None
        if task is None:
            return TaskBatchOpResult(op=kind, status="error", detail="task not found")
        await db.delete(task)
        return TaskBatchOpResult(op="delete", status="ok", task_id=int(task_id))

    return TaskBatchOpResult(op=kind, status="error", detail=f"unknown op {kind!r}")
