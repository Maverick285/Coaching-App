"""Daily-plan generation + per-item state changes.

The "Coach me today" loop, master spec §15. The first time the user
opens Today on a new date, the backend builds today's plan: a list
of goal-derived tasks tiered Must / Should / Could, each with an
estimated time commitment. The model is told strictly:

  - Every task must trace to one of the active goal IDs.
  - No life admin (eating, sleeping, hygiene, errands).
  - Be honest about time estimates.

User actions on items (done / defer / decline) are persisted, and
free-text deferral reasons go through a fast-tier `parse_deferral`
tool call so future plans can take the context into account.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from buddy.llm.client import chat_with_tool
from buddy.llm.models import ModelTier, resolve_model
from buddy.llm.tools import GENERATE_DAILY_PLAN_TOOL, PARSE_DEFERRAL_TOOL
from buddy.logging_setup import get_logger
from buddy.models import (
    ApiUsage,
    DailyPlan,
    DailyPlanItem,
    Goal,
    ProgressLog,
)

log = get_logger("daily_plan")


async def get_or_generate_today(
    db: AsyncSession,
    *,
    today: date | None = None,
) -> DailyPlan:
    """Return today's plan, generating it on first-of-day access.

    No-op fast path if a plan for today already exists. If active
    goals are zero, we still create an empty plan row (so the
    'we tried, you have no goals to plan against' UI state is
    distinguishable from 'we never tried').
    """
    today = today or date.today()
    existing = (
        await db.execute(select(DailyPlan).where(DailyPlan.plan_date == today))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    plan = DailyPlan(plan_date=today, status="active", rationale="")
    db.add(plan)
    await db.flush()
    plan_id = plan.id

    goals_res = await db.execute(
        select(Goal).where(Goal.state == "active", Goal.parent_goal_id.is_(None))
    )
    active_goals: list[Goal] = list(goals_res.scalars().all())
    if not active_goals:
        plan.rationale = "No active goals to plan against."
        await db.commit()
        await db.refresh(plan)
        return plan

    # Pull the last 7 days of progress + the last 14 days of deferred
    # items so the prompt knows what's been worked on and what was
    # punted. The model uses both to choose tasks the user hasn't
    # already crushed and to avoid re-proposing things they explicitly
    # deferred for context-specific reasons.
    week_ago = datetime.combine(today - timedelta(days=7), datetime.min.time())
    progress_res = await db.execute(
        select(ProgressLog).where(ProgressLog.recorded_at >= week_ago)
    )
    recent_progress: list[ProgressLog] = list(progress_res.scalars().all())

    fortnight_ago = today - timedelta(days=14)
    deferred_res = await db.execute(
        select(DailyPlanItem).where(
            DailyPlanItem.state == "deferred",
            DailyPlanItem.created_at >= datetime.combine(fortnight_ago, datetime.min.time()),
        )
    )
    recent_deferred: list[DailyPlanItem] = list(deferred_res.scalars().all())

    user_msg = _build_generation_user_message(
        today=today,
        goals=active_goals,
        recent_progress=recent_progress,
        recent_deferred=recent_deferred,
    )

    model = resolve_model(ModelTier.REASONING)
    payload: dict[str, Any] | None = None
    last_error = ""
    result = None
    for attempt in range(2):
        try:
            result = await chat_with_tool(
                model=model,
                system=DAILY_PLAN_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
                tool=GENERATE_DAILY_PLAN_TOOL,
                max_tokens=2048,
                temperature=0.4 if attempt == 0 else 0.2,
            )
            payload = dict(result.tool_input)
            break
        except Exception as exc:  # noqa: BLE001
            last_error = f"tool call failed: {exc}"
            log.warn("daily_plan.generate_failed", attempt=attempt, error=str(exc))
            continue

    if payload is None or result is None:
        plan.rationale = f"Plan generation failed: {last_error}"
        await db.commit()
        await db.refresh(plan)
        return plan

    db.add(
        ApiUsage(
            provider="anthropic",
            model=result.model,
            operation="daily_plan:generate",
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
        )
    )

    plan.rationale = (payload.get("rationale") or "").strip()
    valid_goal_ids = {g.id for g in active_goals}
    items_in = payload.get("items") or []
    pos = 0
    for raw in items_in:
        try:
            goal_id = int(raw.get("goal_id"))
            tier = str(raw.get("tier", "")).strip().lower()
            est = max(1, min(480, int(raw.get("est_minutes") or 0)))
            text = str(raw.get("task_text", "")).strip()
        except (TypeError, ValueError):
            continue
        if (
            goal_id not in valid_goal_ids
            or tier not in {"must", "should", "could"}
            or not text
        ):
            continue
        db.add(
            DailyPlanItem(
                plan_id=plan_id,
                goal_id=goal_id,
                task_text=text,
                tier=tier,
                est_minutes=est,
                rationale=str(raw.get("rationale") or "").strip(),
                state="pending",
                position=pos,
            )
        )
        pos += 1
    plan.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(plan)
    return plan


async def apply_item_action(
    db: AsyncSession,
    *,
    item_id: int,
    action: str,
    reason: str | None = None,
) -> DailyPlanItem:
    """Mark a plan item done / deferred / declined.

    For 'defer' actions with a free-text reason, kicks the reason
    through `parse_deferral_reason` to extract a structured
    `defer_until` date and a context note. The original free text is
    kept verbatim too so the user can audit later.
    """
    item = await db.get(DailyPlanItem, item_id)
    if item is None:
        raise ValueError(f"daily plan item {item_id} not found")
    item.completed_at = datetime.utcnow()

    if action == "done":
        item.state = "done"
    elif action == "defer":
        item.state = "deferred"
        if reason:
            item.defer_reason = reason.strip()
            await _enrich_defer(item, reason)
    elif action == "decline":
        item.state = "declined"
        if reason:
            item.defer_reason = reason.strip()
    else:
        raise ValueError(f"unknown action {action!r}")

    await db.commit()
    await db.refresh(item)
    return item


async def _enrich_defer(item: DailyPlanItem, reason: str) -> None:
    """Best-effort fast-tier parse of a free-text deferral reason.

    Failures here are swallowed — the verbatim reason is still stored
    on the item, so future plan generations have signal even if the
    structured parse misses.
    """
    try:
        result = await chat_with_tool(
            model=resolve_model(ModelTier.FAST),
            system=PARSE_DEFERRAL_SYSTEM,
            messages=[{"role": "user", "content": f"User said: {reason!r}"}],
            tool=PARSE_DEFERRAL_TOOL,
            max_tokens=256,
            temperature=0.1,
        )
    except Exception as exc:  # noqa: BLE001
        log.warn("daily_plan.parse_defer_failed", error=str(exc))
        return
    payload = result.tool_input
    iso = payload.get("defer_until_iso")
    if isinstance(iso, str) and iso:
        try:
            item.defer_until = date.fromisoformat(iso)
        except ValueError:
            pass
    item.defer_context = str(payload.get("context_note") or "").strip()


# --- Prompt + user-message builders ---------------------------------------

DAILY_PLAN_SYSTEM = """You are running today's plan generation for an
ADHD adult who has saved goals. Your job is to call `generate_daily_plan`
with a tight, honest list of goal-derived tasks for today.

STRICT RULES:

- Every item's `goal_id` MUST be one of the active goals provided.
- NO life admin: no eating, sleeping, hygiene, errands, or anything
  the user didn't explicitly commit to via a saved goal.
- Tier each item:
    must   = if you skip this, today doesn't count toward this goal.
    should = on-pace move; the user is meeting their target if they
             do their `should`s.
    could  = stretch / extra credit / "if you've got the energy."
- Don't pile on. Total `must` + `should` items across all goals
  should be doable in the user's working hours, not theoretical
  hours. Default ceiling: 4 must, 4 should, unlimited could.
- Time estimates are honest minutes. Round 5/10/15. Better to over
  by a bit than to mislead.
- Match each goal's pace target if one is set. If a goal already had
  progress today, you may suggest a top-up but don't double-stack.
- Respect deferred items from the last two weeks: if the user said
  "I'll do that tomorrow while I'm in OKC" three days ago and OKC
  isn't relevant today, fine; if today is the day they meant, lean
  toward including it.
- The `rationale` field is 1-3 sentences in the persona's voice
  about how the day shapes up — not a recap of every item.

Output ONLY the tool call. No prose.
"""


PARSE_DEFERRAL_SYSTEM = """You parse a single short user statement
explaining why they're deferring a task. Extract any defer-until date
the user mentioned (explicit or strongly implied — "tomorrow",
"next Monday", "after the trip on the 8th") and a one-line context
note that captures the why. If no specific date is implied, leave
defer_until_iso null.

Output ONLY the tool call.
"""


def _build_generation_user_message(
    *,
    today: date,
    goals: list[Goal],
    recent_progress: list[ProgressLog],
    recent_deferred: list[DailyPlanItem],
) -> str:
    weekday = today.strftime("%A")
    parts = [f"Today is {today.isoformat()} ({weekday})."]
    parts.append("")
    parts.append("Active goals:")
    for g in goals:
        line = f"- goal_id={g.id}: {g.statement.strip()}"
        if g.pace_target_amount > 0 and g.pace_target_unit:
            line += f"  (pace target: {g.pace_target_amount:g} {g.pace_target_unit}/day)"
        if g.deadline:
            days = (g.deadline - today).days
            line += f"  [deadline {g.deadline.isoformat()}, {days} days out]"
        if g.mvp_threshold:
            line += f"  (no-zero floor: {g.mvp_threshold.strip()})"
        parts.append(line)

    if recent_progress:
        parts.append("")
        parts.append("Progress logged in the last 7 days (most recent first):")
        for p in sorted(recent_progress, key=lambda x: x.recorded_at, reverse=True)[:20]:
            ts = p.recorded_at.strftime("%Y-%m-%d %H:%M")
            parts.append(
                f"- {ts}: goal_id={p.goal_id} — "
                f"{p.attributed_units:g} {p.unit_label or ''} · {p.raw_text!r}"
            )

    if recent_deferred:
        parts.append("")
        parts.append("Recently deferred / declined items the user gave reasons for:")
        for d in sorted(recent_deferred, key=lambda x: x.created_at, reverse=True)[:10]:
            ds = d.created_at.strftime("%Y-%m-%d")
            until = d.defer_until.isoformat() if d.defer_until else "no specific date"
            parts.append(
                f"- {ds}: goal_id={d.goal_id} — {d.task_text!r} · "
                f"defer_until={until} · context={d.defer_context!r}"
            )

    parts.append("")
    parts.append(
        "Generate today's plan. Strict rules apply (no life admin; "
        "every goal_id must come from the active list)."
    )
    return "\n".join(parts)
