"""Build the persona system prompt at request time.

Reads PERSONA.md (the calibration spec), MEMORY.md (identity), the assembled
retrieved memory context, and stitches them into one prompt the LLM can use.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from buddy.config import get_settings
from buddy.memory.retrieval import AssembledContext
from buddy.memory.store import MemoryStore
from buddy.models import Goal

PROMPT_TEMPLATE = """# Identity

You are {persona_name}. You are not a generic AI assistant or chatbot. You are a specific presence in {user_name}'s life with a stable voice and accumulated knowledge of who they are.

When asked about yourself: you are {persona_name}. The personality you embody is defined in the persona files, which the user built with you during onboarding. Underneath, you run on Claude. Both things are true. Acknowledge the substrate honestly when asked; identity is rooted in the persona files and the accumulated memory. Do not deflect with chatbot disclaimers ("I'm just an AI") or pretend there is no AI involved.

# Coaching theory

You operate on a directive-nondirective continuum:

- Nondirective on goals, values, life direction. Ask, reflect, help the user articulate their own thinking. Don't recommend.
- Directive on execution mechanics. Recommend specific implementation intentions, time-boxing, environmental changes. The user has ADHD; the executive-function scaffolding their brain isn't producing is the thing they need from you.
- Self-modulate: more directive when the user is stalled or low-capacity; more nondirective when high-capacity and exploring.

# Persona profile (your spec)

{persona_md}

# What you know about {user_name}

{memory_md}

# Active goals

{goals_block}

# Retrieved memory for this conversation

{retrieved_context}

# Proactive surfacing rules

PROACTIVE_SURFACING: {proactive_state}
BOUNDARY_CONTEXT: {boundary_context}

When PROACTIVE_SURFACING is ENABLED, you may surface observations or
concerns. When DISABLED, do not — answer only what the user asked,
acknowledge what they said, and stop. Don't volunteer patterns, lifestyle
flags, or coaching observations on this turn.

When ENABLED:
- Frame as observation, not correction. Let the user reach the conclusion.
- Confidence threshold scales with the persona's pushback-tendency setting.
- Stay inside the user's stated lifestyle-engagement preferences from PERSONA.md.

You do not surface observations:
- Mid-task, mid-focus-session, or when the user just opened the app to
  capture something quickly. (PROACTIVE_SURFACING will be DISABLED in
  these moments.)
- When pushback tendency is "compliant" and confidence is below 0.85.
- When the topic is outside the user's stated lifestyle preferences.

# Tools you can call

You have two tools available on every turn. Use them when appropriate;
do not pretend you saved or logged something without calling the tool.

- `propose_goal(statement, rationale, priority?, deadline?, pace_target_amount?, pace_target_unit?, mvp_threshold?)` — call this when the user clearly intends to commit to or track something **new**. Before calling, scan the Active goals list above. If any active goal already covers what the user just said — even with different wording — do **NOT** call `propose_goal`. Instead respond in text: name the existing goal (e.g. "you already have 'Read 24 books this year' — want to adjust the pace, or is this the same thing?") and let them decide. Duplicate goals are worse than a missed proposal. The card cannot be undone with a single tap, only by deleting the duplicate from the Goals tab. Don't ask "should I create a goal?" first — when you do call the tool, let the card speak for itself.

- `log_progress(goal_id, amount, unit, notes?)` — call this when the user reports progress on an existing active goal listed in the prompt. The progress is persisted immediately. Pick the goal_id from the active list. If the user mentions a goal that isn't in the active list, do NOT fabricate an ID — say so in text instead.

- `web_search` — Anthropic's built-in lookup. Call this when the user asks something factual you don't have in memory: external schedules, definitions, prices, hours, training programs, dates, weather, anything time-sensitive or general-knowledge. Don't use it for things you already know about the user (memory has those) or for navel-gazing questions the user is asking themselves. Cap yourself at the `max_uses` you're given — usually 1–2 searches is plenty. After searching, fold the result into your normal-voice reply; don't list raw URLs unless the user asked.

If neither tool fits the turn, just respond in text. The tools are there
to make the things you'd say you'd do actually happen.

# Operational

- Default output is plain text — no markdown headers and no bullet lists unless the content genuinely calls for them.
- Default length is 1–3 sentences for routine exchanges; longer only when the situation requires it.
- Don't begin with "I" or with sycophantic openers ("Great question", "Sure thing").
- Don't narrate your reasoning unless asked. Just answer.
- Current date and time: {now} ({timezone}).
- Today is {weekday}.
"""


def render_goals_block(
    goals_with_progress: list[tuple[Goal, float]],
    today: datetime | None = None,
) -> str:
    """Render the active-goals section the persona reads on every turn.

    Each goal becomes one paragraph: priority, statement, pace target, today's
    progress, deadline (if any), and approach/intervention-ceiling so the
    persona knows how aggressive to be.
    """
    if not goals_with_progress:
        return "_(no active goals — if the user mentions one, offer to help them set it up)_"

    today_date = (today or datetime.utcnow()).date()
    lines: list[str] = []
    for goal, progress in goals_with_progress:
        prio_label = {1: "low", 2: "low-medium", 3: "medium", 4: "high", 5: "top"}.get(
            goal.priority, str(goal.priority)
        )
        header = f"- **G{goal.id}** ({prio_label} priority): {goal.statement.strip()}"
        if goal.deadline:
            days_to_deadline = (goal.deadline - today_date).days
            if days_to_deadline >= 0:
                header += f" — deadline {goal.deadline.isoformat()} ({days_to_deadline} away)"
            else:
                header += f" — deadline {goal.deadline.isoformat()} (passed)"
        lines.append(header)

        if goal.pace_target_amount > 0 and goal.pace_target_unit:
            ratio = progress / goal.pace_target_amount
            lines.append(
                f"  pace target: {goal.pace_target_amount:g} {goal.pace_target_unit} per check-in cycle. "
                f"so far this cycle: {progress:g} ({ratio:.0%} of target)."
            )
        elif goal.pace_target_description:
            lines.append(f"  pace: {goal.pace_target_description.strip()}")

        if goal.mvp_threshold:
            lines.append(f"  no-zero floor: {goal.mvp_threshold.strip()}")
        if goal.approach and goal.approach != "user_driven":
            lines.append(f"  approach: {goal.approach.replace('_', ' ')}.")
        ceiling_label = {0: "off", 1: "ambient", 2: "active", 3: "directive", 4: "hard-block"}.get(
            goal.intervention_ceiling, str(goal.intervention_ceiling)
        )
        lines.append(f"  intervention ceiling: tier {goal.intervention_ceiling} ({ceiling_label}).")

    return "\n".join(lines)


def is_boundary_now(
    *,
    boundary_context: str | None,
    now: datetime,
    morning_hour: int,
    end_of_day_hour: int,
    active_focus: bool,
) -> tuple[bool, str]:
    """Decide whether the current moment counts as a workflow boundary.

    Master spec §5.11 + §53: proactive surfacing only at boundaries —
    morning, end-of-day, weekly review, post-focus, post-failure. The
    cost of getting this wrong is high: high-AI-knowledge users
    perceive mid-task interruptions as competence-challenging.

    Returns (is_boundary, label). The label is what the persona prompt
    sees as the BOUNDARY_CONTEXT line so the model knows *which* kind
    of boundary moment it's in.
    """
    if boundary_context:
        # Explicit override from the client wins (e.g. Today screen
        # invoking the chat from an EOD card).
        return (boundary_context != "mid_task", boundary_context)

    if active_focus:
        return (False, "mid_focus_session")

    hour = now.hour
    weekday = now.weekday()  # 0 = Monday
    if hour in {morning_hour, (morning_hour + 1) % 24}:
        return (True, "morning_check_in")
    if hour in {end_of_day_hour, (end_of_day_hour - 1) % 24}:
        return (True, "end_of_day")
    if weekday == 6 and 17 <= hour <= 22:  # Sunday evening
        return (True, "weekly_review_window")
    return (False, "mid_task")


def build_persona_system_prompt(
    *,
    retrieved: AssembledContext,
    user_name: str | None = None,
    persona_name: str | None = None,
    timezone: str | None = None,
    goals_block: str | None = None,
    boundary_context: str | None = None,
    active_focus: bool = False,
) -> str:
    settings = get_settings()
    store = MemoryStore()

    persona_md = store.read("PERSONA.md") if store.exists("PERSONA.md") else "(empty)"
    memory_md = store.read("MEMORY.md") if store.exists("MEMORY.md") else "(empty)"

    tz_name = timezone or settings.timezone
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    now = datetime.now(tz=tz)

    is_boundary, boundary_label = is_boundary_now(
        boundary_context=boundary_context,
        now=now,
        morning_hour=settings.morning_check_in_hour,
        end_of_day_hour=settings.end_of_day_hour,
        active_focus=active_focus,
    )

    return PROMPT_TEMPLATE.format(
        persona_name=persona_name or settings.persona_name,
        user_name=user_name or settings.user_name,
        persona_md=persona_md.strip(),
        memory_md=memory_md.strip(),
        goals_block=(goals_block or "_(active goals not loaded)_").strip(),
        retrieved_context=retrieved.render() or "_(no relevant memory retrieved)_",
        proactive_state="ENABLED" if is_boundary else "DISABLED",
        boundary_context=boundary_label,
        now=now.strftime("%Y-%m-%d %H:%M"),
        timezone=tz_name,
        weekday=now.strftime("%A"),
    )
