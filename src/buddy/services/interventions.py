"""Drift detection + tier-0/1/2 escalation engine.

Invariants per spec §6:

  - Engine only runs while a focus session is active.
  - For each active session, look at the goal's distraction rules.
  - If the most recent contiguous run of "distractor" agent reports for that
    session is ≥ cooldown_seconds long, and there is no live (un-dismissed)
    intervention for this drift episode, fire Tier 0.
  - If a tier-N intervention has been live for ≥ ESCALATION_GAP_SECONDS,
    fire tier N+1 (cap at tier 2 for Phase 4; tiers 3-5 are Phase 5).
  - Anything fired is persisted; the phone polls /interventions/pending.

This module is pure logic on top of the DB. The scheduler calls
`run_engine_tick` every ~30 seconds.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from buddy.models import (
    AgentReport,
    DistractionRule,
    FocusSession,
    Goal,
    Intervention,
)

ESCALATION_GAP_SECONDS = 60  # spec says "30-60s gap"; 60s is the safer default
MAX_TIER_PHASE_5 = 4          # 0/1/2 = nudges, 3 = friction, 4 = hard block
DEFAULT_INTERVENTION_CEILING = 2


@dataclass
class DriftEpisode:
    """How long the user has been in a distractor category, contiguously,
    according to the most recent agent reports for this session."""

    session_id: int
    distractor_category: str
    cooldown_seconds: int
    contiguous_seconds: int
    last_report_at: datetime


# --- detection -----------------------------------------------------------


async def _distraction_rules(session: AsyncSession, goal_id: int) -> list[DistractionRule]:
    rows = await session.execute(
        select(DistractionRule).where(
            DistractionRule.goal_id == goal_id,
            DistractionRule.is_active.is_(True),
        )
    )
    return list(rows.scalars().all())


async def _recent_reports(
    session: AsyncSession,
    focus_session_id: int,
    look_back_seconds: int = 600,
) -> list[AgentReport]:
    cutoff = datetime.utcnow() - timedelta(seconds=look_back_seconds)
    rows = await session.execute(
        select(AgentReport)
        .where(
            AgentReport.session_id == focus_session_id,
            AgentReport.received_at >= cutoff,
        )
        .order_by(AgentReport.received_at.asc())
    )
    return list(rows.scalars().all())


def _episode_duration(
    reports: list[AgentReport], distractor_categories: set[str]
) -> tuple[int, str | None, datetime | None]:
    """Walk reports newest→oldest, sum the most recent contiguous run of
    distractor categories. Returns (seconds, category, last_report_at).

    The agent reports every ~10s with `active_seconds` describing how long
    its foreground was in that category since the last report; we sum
    those values across the contiguous tail to get the run length.
    """
    if not reports:
        return (0, None, None)
    latest = reports[-1]
    if latest.foreground_category not in distractor_categories:
        return (0, None, latest.received_at)
    cat = latest.foreground_category
    contiguous_seconds = 0
    for r in reversed(reports):
        if r.foreground_category != cat:
            break
        # Each report covers `active_seconds` of foreground time. Floor at
        # 1 so a series of zero-active-seconds reports still adds up to
        # something visible.
        contiguous_seconds += max(1, int(r.active_seconds))
    return (contiguous_seconds, cat, latest.received_at)


async def detect_drift_for_session(
    session: AsyncSession, focus_session: FocusSession
) -> DriftEpisode | None:
    if focus_session.goal_id is None:
        return None
    rules = await _distraction_rules(session, focus_session.goal_id)
    if not rules:
        return None
    distractor_categories = {r.distractor_category for r in rules}
    cooldown_by_cat = {r.distractor_category: r.cooldown_seconds for r in rules}

    reports = await _recent_reports(session, focus_session.id)
    seconds, cat, last_at = _episode_duration(reports, distractor_categories)
    if cat is None or last_at is None:
        return None
    cooldown = cooldown_by_cat.get(cat, 90)
    if seconds < cooldown:
        return None
    return DriftEpisode(
        session_id=focus_session.id,
        distractor_category=cat,
        cooldown_seconds=cooldown,
        contiguous_seconds=seconds,
        last_report_at=last_at,
    )


# --- escalation -----------------------------------------------------------


async def _live_drift_intervention(
    session: AsyncSession, focus_session_id: int, reason_prefix: str
) -> Intervention | None:
    """The most recent un-dismissed intervention for this session whose reason
    matches the prefix. Used to dedupe drift episodes and to find the next
    escalation target."""
    rows = await session.execute(
        select(Intervention)
        .where(
            Intervention.session_id == focus_session_id,
            Intervention.dismissed_at.is_(None),
            Intervention.reason.startswith(reason_prefix),
        )
        .order_by(Intervention.fired_at.desc())
    )
    return rows.scalars().first()


async def _was_recently_dismissed(
    session: AsyncSession,
    *,
    focus_session_id: int,
    reason: str,
    within_seconds: int,
) -> bool:
    """True if any matching intervention was dismissed within the window.
    Used as a post-dismissal grace period so the engine doesn't immediately
    re-fire the same drift reason after the user explicitly closed it.

    Tier escalation uses dismissed_at internally to mark "superseded by
    next tier"; we exclude those by requiring next_escalation_at IS NULL,
    since escalation supersession sets that field, while a real user
    dismissal does not.
    """
    cutoff = datetime.utcnow() - timedelta(seconds=within_seconds)
    rows = await session.execute(
        select(Intervention).where(
            Intervention.session_id == focus_session_id,
            Intervention.reason == reason,
            Intervention.dismissed_at.is_not(None),
            Intervention.dismissed_at >= cutoff,
            Intervention.next_escalation_at.is_(None),
        )
    )
    return rows.scalars().first() is not None


def _drift_message(tier: int, category: str) -> str:
    if tier == 0:
        return f"You drifted into {category}. Back to the work?"
    if tier == 1:
        return f"Still in {category}. The next move is the file. Open it."
    if tier == 2:
        return f"Two minutes in {category}. The session is yours. Take it back."
    if tier == 3:
        return f"Friction is on for {category}. Sixty-second pause before you go further."
    return f"{category} is blocked for the rest of the session. Override if it's real."


def _floor_message(tier: int, goal_statement: str) -> str:
    if tier == 0:
        return f"No movement on “{goal_statement[:60]}” today. One step counts."
    if tier == 1:
        return f"Still nothing on “{goal_statement[:60]}”. Smallest move?"
    return f"This is the last nudge on “{goal_statement[:60]}” today."


async def _fire_or_escalate(
    session: AsyncSession,
    *,
    focus_session_id: int | None,
    goal_id: int | None,
    reason: str,
    base_message_for_tier: Callable[[int], str],
) -> Intervention | None:
    """Either fire Tier 0 (if no live intervention), or escalate the live one
    if its grace period elapsed. Returns the new/updated row, or None if
    nothing happened this tick."""
    now = datetime.utcnow()
    if focus_session_id is not None:
        live = await _live_drift_intervention(session, focus_session_id, reason)
    else:
        # Floor checks aren't tied to a session; dedupe on (goal_id, reason).
        rows = await session.execute(
            select(Intervention)
            .where(
                Intervention.goal_id == goal_id,
                Intervention.dismissed_at.is_(None),
                Intervention.reason == reason,
            )
            .order_by(Intervention.fired_at.desc())
        )
        live = rows.scalars().first()

    if live is None:
        new = Intervention(
            session_id=focus_session_id,
            goal_id=goal_id,
            tier=0,
            fired_at=now,
            next_escalation_at=now + timedelta(seconds=ESCALATION_GAP_SECONDS),
            reason=reason,
            message=base_message_for_tier(0),
        )
        session.add(new)
        await session.flush()
        return new

    # Resolve the per-goal ceiling — defaults to 2 (no friction/hard block
    # unless the user explicitly opted in by raising the ceiling).
    ceiling = DEFAULT_INTERVENTION_CEILING
    if live.goal_id is not None:
        goal = await session.get(Goal, live.goal_id)
        if goal is not None:
            ceiling = max(0, min(MAX_TIER_PHASE_5, goal.intervention_ceiling))

    # We have a live one — escalate if grace elapsed and we have headroom.
    if (
        live.next_escalation_at is not None
        and now >= live.next_escalation_at
        and live.tier < ceiling
    ):
        new_tier = live.tier + 1
        escalated = Intervention(
            session_id=live.session_id,
            goal_id=live.goal_id,
            tier=new_tier,
            fired_at=now,
            next_escalation_at=(
                now + timedelta(seconds=ESCALATION_GAP_SECONDS)
                if new_tier < ceiling
                else None
            ),
            reason=reason,
            message=base_message_for_tier(new_tier),
        )
        # Mark the previous tier as superseded (dismissed by the system).
        live.dismissed_at = now
        session.add(escalated)
        await session.flush()
        return escalated

    return None


# --- public engine entry point -------------------------------------------


@dataclass
class TickResult:
    drift_fired: list[Intervention]
    floor_fired: list[Intervention]


async def run_engine_tick(session: AsyncSession) -> TickResult:
    """One pass: drift detection across all active sessions + (optional)
    daily-floor checks. Idempotent: safe to run every 30 seconds."""
    drift_fired: list[Intervention] = []
    floor_fired: list[Intervention] = []

    # Phase 5: if an override window is open, the engine takes a breath.
    # The user just bought 15 minutes of grace from the approver; nagging
    # them with new drift fires would make the override pointless.
    from buddy.services.overrides import get_active_override

    if (await get_active_override(session)) is not None:
        return TickResult(drift_fired=[], floor_fired=[])

    active_sessions = (
        await session.execute(
            select(FocusSession).where(FocusSession.state == "active")
        )
    ).scalars().all()

    for fs in active_sessions:
        episode = await detect_drift_for_session(session, fs)
        if episode is None:
            # If no drift, mark any live drift intervention as dismissed
            # (user came back). Clear next_escalation_at so this row is
            # tagged as a "real" dismissal rather than a tier supersession.
            live = await _live_drift_intervention(
                session, fs.id, reason_prefix="drift:"
            )
            if live is not None:
                live.dismissed_at = datetime.utcnow()
                live.next_escalation_at = None
            continue

        # Post-dismissal grace period: if the user just dismissed the same
        # drift reason recently, don't immediately re-fire — give them
        # cooldown_seconds * 2 of room before nagging again.
        reason = f"drift:{episode.distractor_category}"
        if await _was_recently_dismissed(
            session,
            focus_session_id=fs.id,
            reason=reason,
            within_seconds=episode.cooldown_seconds * 2,
        ):
            continue

        result = await _fire_or_escalate(
            session,
            focus_session_id=fs.id,
            goal_id=fs.goal_id,
            reason=reason,
            base_message_for_tier=lambda t: _drift_message(t, episode.distractor_category),
        )
        if result is not None:
            drift_fired.append(result)

    await session.commit()
    return TickResult(drift_fired=drift_fired, floor_fired=floor_fired)


async def run_floor_check(session: AsyncSession, day: date | None = None) -> list[Intervention]:
    """Daily floor check: for each active goal, if no progress today,
    fire a Tier 0 floor intervention. Goals opted into Tier 5
    stake-at-risk additionally trigger their pre-committed webhook so
    Beeminder/IFTTT/Zapier can act on the no-zero-day break.
    """
    from buddy.models import ProgressLog
    from buddy.services.stakes import fire_stake_webhook

    today = day or date.today()
    start = datetime(today.year, today.month, today.day)
    end = start + timedelta(days=1)

    fired: list[Intervention] = []
    stake_fires: list[int] = []
    goals = (
        await session.execute(select(Goal).where(Goal.state == "active"))
    ).scalars().all()
    for goal in goals:
        progress_rows = (
            await session.execute(
                select(ProgressLog).where(
                    ProgressLog.goal_id == goal.id,
                    ProgressLog.recorded_at >= start,
                    ProgressLog.recorded_at < end,
                )
            )
        ).scalars().all()
        if any(p.attributed_units > 0 for p in progress_rows):
            continue
        result = await _fire_or_escalate(
            session,
            focus_session_id=None,
            goal_id=goal.id,
            reason=f"floor_check:{today.isoformat()}",
            base_message_for_tier=lambda t: _floor_message(t, goal.statement),
        )
        if result is not None:
            fired.append(result)
        # Tier 5: opt-in stake webhook fires alongside the floor
        # intervention, regardless of intervention_ceiling. The stake is
        # the user's pre-commitment, not an escalation rung.
        if goal.stake_active and goal.stake_webhook_url:
            stake_fires.append(goal.id)
    await session.commit()

    for goal_id in stake_fires:
        await fire_stake_webhook(
            goal_id=goal_id,
            event_kind="zero_day_floor_break",
            payload={"day": today.isoformat()},
        )
    return fired
