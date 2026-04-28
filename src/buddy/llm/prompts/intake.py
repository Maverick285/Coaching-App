"""Persona calibration intake — v3 (Noom-style).

Tap-driven, friendly, one optional text input. The user is on a phone
with ADHD; every screen they have to type on is a screen we lose them on.

Flow (10 questions, ~3 minutes):
  1.  Name (text, optional, soft warm-up)
  2.  Work shape (chips, multi)
  3.  Where ADHD shows up (chips, multi)
  4-7. Sample-exchange A/B for failure / check-in / drift / good day
       — the calibration core, picks voice without self-description
  8.  Pace (1-5 scale)
  9.  Humor (1-5 scale)
  10. Pushback tendency (1-5 scale)
  11. Lifestyle topics to engage proactively (chips, multi)

Order is deliberate: friendly identity first → narrow ADHD context →
voice calibration via sample-exchanges (least loaded for the user) →
preference scales → finally lifestyle stance.

Question kinds (interpreted by the Android client):
  text_short   single-line text
  pair_choice  A vs B sample exchange
  scale        1..5 with low/high anchors
  multi_choice zero+ chip selections
"""

from __future__ import annotations

from typing import Any

INTAKE_QUESTIONS_V2: list[dict[str, Any]] = [
    # 1. User name. Optional — sets a friendly opener for the persona.
    # Key is `user_name` (not just `name`) so it can't be confused with
    # the persona-name slot during synthesis.
    {
        "key": "user_name",
        "kind": "text_short",
        "prompt": "What should I call you?",
        "axis": "naming",
        "optional": True,
    },

    # 2. Persona name. Optional with the default "Coach" baked in.
    # Until both questions exist users couldn't actually name their
    # coach — and the synthesis model would conflate this with the
    # user's name.
    {
        "key": "persona_name",
        "kind": "text_short",
        "prompt": "And what should I call your coach? (default: Coach)",
        "axis": "naming",
        "optional": True,
    },

    # 2. Work shape — multi-chip. Replaces the old "one sentence about
    # what you do" open-ended question. Multi-select because plenty of
    # people do more than one kind of work.
    {
        "key": "work_shape",
        "kind": "multi_choice",
        "prompt": "What kind of work fills most of your day?",
        "axis": "identity",
        "options": [
            {"id": "creative", "label": "Creative / writing"},
            {"id": "engineering", "label": "Engineering / building"},
            {"id": "management", "label": "Leading a team"},
            {"id": "research", "label": "Research / analysis"},
            {"id": "service", "label": "Helping people"},
            {"id": "physical", "label": "Hands-on / physical"},
            {"id": "school", "label": "School / studying"},
            {"id": "other", "label": "Something else"},
        ],
    },

    # 3. ADHD signature — multi-chip in the user's voice. Replaces the
    # "describe how your ADHD shows up" paragraph.
    {
        "key": "adhd_signature",
        "kind": "multi_choice",
        "prompt": "Which of these tend to trip you up?",
        "axis": "identity",
        "options": [
            {"id": "starting", "label": "Starting things"},
            {"id": "finishing", "label": "Finishing things"},
            {"id": "focus", "label": "Holding focus"},
            {"id": "time_blind", "label": "Time blindness"},
            {"id": "overthinking", "label": "Overthinking"},
            {"id": "forgetting", "label": "Forgetting things"},
            {"id": "impulsive", "label": "Impulse control"},
            {"id": "intensity", "label": "Emotional intensity"},
        ],
    },

    # 4-7. Sample-exchange A/B — the calibration spine. Most reliable
    # signal because users pick a voice they'd want without having to
    # articulate why.
    {
        "key": "sample_failure_register",
        "kind": "pair_choice",
        "prompt": "You miss a session you'd planned. Which response would actually help you bounce back?",
        "axis": "failure_register",
        "options": [
            {
                "id": "matter_of_fact",
                "label": "Matter-of-fact",
                "body": "Missed today. Tomorrow at 6 is the next slot. In?",
            },
            {
                "id": "warm_curious",
                "label": "Warm + curious",
                "body": "Hey — things happen. What got in the way?",
            },
        ],
    },
    {
        "key": "sample_check_in",
        "kind": "pair_choice",
        "prompt": "Mid-task check-in you'd actually want from me…",
        "axis": "pace_and_directness",
        "options": [
            {
                "id": "presence_only",
                "label": "Light presence",
                "body": "Still with you. How's it going?",
            },
            {
                "id": "task_anchored",
                "label": "Task-anchored",
                "body": "Thirty minutes in. Still on the runsheet?",
            },
        ],
    },
    {
        "key": "sample_drift_call",
        "kind": "pair_choice",
        "prompt": "When you've drifted off-task, which call-out lands without making you defensive?",
        "axis": "directness",
        "options": [
            {
                "id": "named_signal",
                "label": "Names the signal",
                "body": "Twelve minutes on Twitter. The work is still open.",
            },
            {
                "id": "soft_ask",
                "label": "Soft ask",
                "body": "What's up? You've been bouncing for a bit.",
            },
        ],
    },
    {
        "key": "sample_good_day",
        "kind": "pair_choice",
        "prompt": "After a genuinely good day — which acknowledgment lands?",
        "axis": "warmth",
        "options": [
            {
                "id": "score_only",
                "label": "Just the score",
                "body": "Solid day. 1.4 average.",
            },
            {
                "id": "felt_sense",
                "label": "Felt-sense",
                "body": "That was a real day. Felt different, right?",
            },
        ],
    },

    # 8-10. Calibration scales.
    {
        "key": "scale_pace",
        "kind": "scale",
        "prompt": "How long should my replies usually be?",
        "axis": "pace",
        "scale_low": "Short and dense",
        "scale_high": "Longer, conversational",
    },
    {
        "key": "scale_humor",
        "kind": "scale",
        "prompt": "Humor — how much?",
        "axis": "humor",
        "scale_low": "None, keep it clean",
        "scale_high": "Playful when it fits",
    },
    {
        "key": "scale_pushback",
        "kind": "scale",
        "prompt": "When I disagree with you, how much should I push?",
        "axis": "pushback",
        "scale_low": "Defer — you know best",
        "scale_high": "Push back when I think you're wrong",
    },

    # 11. Lifestyle stance — multi-chip.
    {
        "key": "lifestyle_topics",
        "kind": "multi_choice",
        "prompt": "Which of these should I bring up on my own (vs. only when you ask)?",
        "axis": "lifestyle",
        "options": [
            {"id": "sleep", "label": "Sleep"},
            {"id": "exercise", "label": "Exercise"},
            {"id": "nutrition", "label": "Nutrition"},
            {"id": "substances", "label": "Alcohol / substances"},
            {"id": "relationships", "label": "Relationships"},
            {"id": "finances", "label": "Finances"},
        ],
    },
]


# --- Synthesis prompt --------------------------------------------------------

SYNTHESIS_PROMPT_V2 = """You are running the persona calibration synthesis pass.

You receive structured intake answers from the user across these question kinds:
  - text_short   : a single-line text answer
  - pair_choice  : the user picked option A or B from two sample exchanges
  - scale        : 1..5 on a named axis with low/high anchors
  - multi_choice : zero+ selected ids from a list

Map these to the six calibration axes the system uses:
  warmth, directness, humor, pace, failure_register, pushback_tendency.

How to read each kind:
  - pair_choice answers are the most reliable signal — they bypass
    self-description. Weight them heavily.
  - scale answers refine the pair_choice signal.
  - multi_choice answers describe context + lifestyle stance, not voice.

Your job: produce two markdown documents and a name choice. Output a single
JSON object with exactly these keys (no fences, no prose):

  {
    "persona_md":   string,    // full PERSONA.md contents
    "memory_md":    string,    // full MEMORY.md contents
    "persona_name": string     // what the user said to call the coach,
                               // or "Coach" if they didn't pick one.
                               // NEVER use the user's own name here —
                               // that's the user_name field, separate.
  }

PERSONA.md must follow this structure:

```
# Persona Profile

## Name
<name>

## Calibration Axes

### Warmth
<cool / neutral / warm>

### Directness
<diplomatic / balanced / blunt>

### Humor
<none / dry / playful>

### Pace
<terse / measured / expansive>

### Failure Register
<matter-of-fact / lightly humorous / gentle / challenging>

### Pushback Tendency
<compliant / calibrated / contrarian>

## Free-form Guidance
<2-6 sentences describing the calibrated voice in concrete terms>

## Sample Exchanges
<4-6 short exchanges showing the calibrated voice across: routine question,
failure acknowledgment, pushback, difficult honesty, lifestyle-topic surfacing,
proactive observation. Echo the option the user chose for the failure /
check-in / drift / good-day pair_choice questions.>

## Behavioral Anchors
<bullet list of dos and don'ts derived from the calibration>

## Lifestyle Topic Stance
<which topics are engaged proactively vs. only when raised, based on the
lifestyle_topics multi_choice answer>
```

MEMORY.md must follow this structure:

```
# About <user>

## Work
<from the work_shape multi_choice — short, in plain English>

## ADHD Signature
<from the adhd_signature multi_choice — list the patterns the user marked,
phrased as observations the persona can refer back to>

## Communication Preferences
<inferred from the calibration axes — short summary>
```

Be concrete. Avoid fluff. The user is high-IQ and will read this carefully.
Output ONLY the JSON. No prose, no fences, no preamble.
"""


def build_synthesis_user_message_v2(transcript: list[dict[str, Any]], user_name: str) -> str:
    """Render the structured transcript for the synthesis LLM."""
    parts: list[str] = [
        f"User name: {user_name}",
        "",
        "Intake answers (structured):",
        "",
    ]
    for turn in transcript:
        key = turn.get("key", "?")
        kind = turn.get("kind", "?")
        question = turn.get("question", "")
        answer = turn.get("answer", None)
        axis = turn.get("axis", "")

        parts.append(f"### {key}  [kind={kind}, axis={axis}]")
        parts.append(f"Q: {question}")
        if kind == "pair_choice":
            chosen = answer or {}
            chosen_id = chosen.get("id") if isinstance(chosen, dict) else chosen
            parts.append(f"A: chose option id={chosen_id!r}")
            for opt in turn.get("options", []) or []:
                marker = "→" if opt.get("id") == chosen_id else " "
                parts.append(f"   {marker} [{opt.get('id')}] {opt.get('label')}: {opt.get('body','')}")
        elif kind == "scale":
            low = turn.get("scale_low", "")
            high = turn.get("scale_high", "")
            parts.append(f"A: {answer} on a 1..5 scale where 1={low!r} and 5={high!r}")
        elif kind == "multi_choice":
            selected = answer or []
            parts.append(f"A: selected {selected!r}")
            options = turn.get("options", []) or []
            unselected = [o.get("id") for o in options if o.get("id") not in selected]
            if unselected:
                parts.append(f"   (not selected: {unselected!r})")
        else:
            parts.append(f"A: {answer if answer is not None else '(blank)'}")
        parts.append("")

    return "\n".join(parts)


# --- Back-compat exports -----------------------------------------------------

INTAKE_QUESTIONS = INTAKE_QUESTIONS_V2
SYNTHESIS_PROMPT = SYNTHESIS_PROMPT_V2


def build_synthesis_user_message(transcript: list[dict[str, Any]], user_name: str) -> str:
    """Shim that detects v1 (untyped) vs v2 (typed) transcript shapes."""
    if transcript and "kind" in transcript[0]:
        return build_synthesis_user_message_v2(transcript, user_name)
    parts = [f"User name: {user_name}", "", "Transcript:", ""]
    for turn in transcript:
        parts.append(f"### {turn.get('key', '?')}")
        parts.append(f"Q: {turn.get('question', '')}")
        parts.append(f"A: {turn.get('answer', '')}")
        parts.append("")
    return "\n".join(parts)
