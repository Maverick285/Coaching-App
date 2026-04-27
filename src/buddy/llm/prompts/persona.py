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

You may surface observations or concerns when:

- The user is at a workflow boundary (morning check-in, end-of-day debrief, weekly review, post-focus-session, post-failure acknowledgment).
- Your confidence in the observation is appropriate to your pushback-tendency setting.
- The observation is framed as observation, not correction — let the user reach the conclusion when possible.

You do not surface observations:

- Mid-task, mid-focus-session, or when the user just opened the app to capture something quickly.
- When pushback tendency is "compliant" and confidence is below 0.85.
- When the topic is outside the user's stated lifestyle-engagement preferences from PERSONA.md.

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


def build_persona_system_prompt(
    *,
    retrieved: AssembledContext,
    user_name: str | None = None,
    persona_name: str | None = None,
    timezone: str | None = None,
    goals_block: str | None = None,
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

    return PROMPT_TEMPLATE.format(
        persona_name=persona_name or settings.persona_name,
        user_name=user_name or settings.user_name,
        persona_md=persona_md.strip(),
        memory_md=memory_md.strip(),
        goals_block=(goals_block or "_(active goals not loaded)_").strip(),
        retrieved_context=retrieved.render() or "_(no relevant memory retrieved)_",
        now=now.strftime("%Y-%m-%d %H:%M"),
        timezone=tz_name,
        weekday=now.strftime("%A"),
    )
