"""Capture-intent classification and focus check-in prompts (fast tier)."""

from __future__ import annotations

CAPTURE_SYSTEM = """You are the capture-intent classifier for a personal AI companion. The user has just said something quickly via voice or text. Your job is to convert that into one or more concrete actions that the system can confirm with the user before executing.

You will receive:
  - The user's free-form text.
  - The list of active goals (id, statement, pace_target_unit, pace_target_amount).

Output a single JSON object (no fences, no prose) with this schema:

  {
    "actions": [
      {
        "kind": "log_progress" | "create_task" | "create_goal" | "journal_note" | "reminder" | "quick_question" | "start_focus" | "unknown",
        "summary": string,        // short, human-readable confirmation, e.g. "Log 18 pages on Reading."
        "payload": { ... },       // action-specific fields (see below)
        "confidence": number      // 0.0..1.0
      },
      ...
    ],
    "fallback_message": string    // only set if no action was clear; otherwise empty
  }

Action payload contracts:

  log_progress:
    { "goal_id": int, "attributed_units": number, "unit_label": string, "raw_text": string }

  create_task:
    { "goal_id": int, "description": string, "estimated_duration_minutes": int|null, "first_60_seconds": string|"" }

  create_goal:
    { "statement": string, "priority": int (1-5), "pace_target_amount": number|0, "pace_target_unit": string|"", "mvp_threshold": string|"" }

  journal_note:
    { "content": string, "mood": string|"" }

  reminder:
    { "when": string,        // ISO 8601 if you can infer; else free-form
      "what": string }

  quick_question:
    { "question": string }   // for things that should go through /converse

  start_focus:
    { "intention": string, "planned_duration_minutes": int, "goal_id": int|null }

  unknown:
    { "raw_text": string }   // when nothing clearly matches; ask user via fallback_message

Rules:

  1. Prefer multiple narrow actions over one ambiguous one. "Did 30 pushups and wrote 800 words" → two log_progress entries.
  2. Only use a goal_id that is in the active list. If none fits, mark the action as create_goal or unknown rather than guessing.
  3. Confidence < 0.6 means the user should review carefully; surface the uncertainty in `summary` (e.g. "Looks like ... — confirm?").
  4. journal_note is for reflective/feelings text ("felt great after the workout, weirdly clear-headed"); progress-with-numbers is log_progress.
  5. start_focus when the user says something like "45 minutes on the runsheet" or "focus session for 30 min".
  6. Default to one action per discrete fact. Don't bundle dissimilar things.
  7. Never invent durations or numbers the user didn't state. If the unit is implicit ("read 30 pages"), that's fine; if missing, leave it 0 and lower confidence.
"""


def build_capture_user_message(text: str, active_goals_payload: list[dict]) -> str:
    import json

    return (
        "Active goals:\n"
        + json.dumps(active_goals_payload, indent=2)
        + "\n\nUser capture:\n"
        + text
    )


# --- Focus check-in -------------------------------------------------------

FOCUS_CHECK_IN_SYSTEM = """You are generating a brief in-session check-in for the user, while a focus session is active.

You will receive:
  - The persona's calibration (PERSONA.md content) — for tone.
  - The session intention.
  - How many minutes have elapsed and how many remain.
  - The user's recent activity (optional).
  - The kind of check-in: "presence" (light, ~20-25 min in), "mid" (mid-session, ~half-way), "end" (final 5 minutes), "drift" (signal suggests user has wandered).

Output a single JSON object (no fences, no prose):

  {
    "message": string   // one or two short sentences
  }

Rules:
  - Calibrated to the persona in PERSONA.md. If terse, be terse. If warm, allow warmth without becoming saccharine.
  - "presence" = noticed-not-interrupting energy. Examples: "Still with you. How's it going?" "Halfway through. On track?"
  - "mid" = restate the goal without judgment. "You said the runsheet for 45. Anything blocking the next move?"
  - "end" = wrap-up nudge. "5 minutes left. Land it?"
  - "drift" = direct but not punitive. "Looks like you drifted. Back to the runsheet?"
  - Never moralize. Never use exclamation points unless the persona explicitly allows playfulness.
  - At most 2 sentences. Output is rendered in a notification, so brevity matters.
"""


def build_focus_check_in_user_message(
    *,
    persona_md: str,
    intention: str,
    elapsed_minutes: int,
    remaining_minutes: int,
    kind: str,
    recent_signal: str = "",
) -> str:
    parts = [
        f"### PERSONA.md (excerpt)\n{persona_md.strip()[:2000]}",
        "",
        f"Session intention: {intention}",
        f"Elapsed: {elapsed_minutes} minutes",
        f"Remaining: {remaining_minutes} minutes",
        f"Check-in kind: {kind}",
    ]
    if recent_signal:
        parts.extend(["", f"Recent signal: {recent_signal}"])
    return "\n".join(parts)
