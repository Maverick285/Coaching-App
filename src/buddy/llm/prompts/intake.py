"""Persona calibration intake — v2.

Designed for ADHD users: tap-driven, paired-sample choices for the bits
that matter, scales for axes that have established research lineage,
and only a handful of short text inputs. ~12 prompts total, ~5 minutes.

Maps to the six calibration axes the spec defined (warmth, directness,
humor, pace, failure register, pushback tendency), grounded in the
coaching/therapy research the spec cites (Passmore 2010 + Ives 2008 on
the directive-nondirective continuum, Knouse on CBT-for-ADHD,
therapeutic-alliance work on bond-via-paired-samples).

Question kinds:
  - text_short  — single-line text (name, one-liner)
  - text_long   — paragraph
  - pair_choice — A vs B sample exchange; user picks the one that
                  feels right. Most reliable signal (bypasses
                  self-description).
  - scale       — 5-point scale on a named axis with low/high anchors.
  - multi_choice — pick zero or more from a list (lifestyle topics).
"""

from __future__ import annotations

from typing import Any

# Schema-as-dicts so it's easy to ship to the Android client without an
# enum-roundtrip; the client just renders by `kind`.
INTAKE_QUESTIONS_V2: list[dict[str, Any]] = [
    # --- Section 1: Identity (3 short text answers) -----------------------
    {
        "key": "name",
        "kind": "text_short",
        "prompt": "What should I call you? Your first name or a nickname you like. Leave blank to stay 'Coach'.",
        "axis": "naming",
        "optional": True,
    },
    {
        "key": "occupation",
        "kind": "text_short",
        "prompt": "One sentence: what do you do?",
        "axis": "identity",
        "optional": False,
    },
    {
        "key": "adhd_pattern",
        "kind": "text_long",
        "prompt": "Briefly: how does your ADHD show up day-to-day? No need to be clinical — 'great at hyperfocus, terrible at starting' kind of answer is great.",
        "axis": "identity",
        "optional": False,
    },

    # --- Section 2: Sample-exchange A/B (4 pairs) -------------------------
    # The spec calls for sample-exchange ratings explicitly. Most reliable
    # calibration signal because users pick a voice they'd want without
    # having to articulate why.
    {
        "key": "sample_failure_register",
        "kind": "pair_choice",
        "prompt": "After you miss a session you said you'd do, the response that would actually help you get back on the horse is...",
        "axis": "failure_register",
        "options": [
            {
                "id": "matter_of_fact",
                "label": "Matter-of-fact",
                "body": "You missed today. Tomorrow at 6 is the next slot. In?",
            },
            {
                "id": "warm_curious",
                "label": "Warm + curious",
                "body": "Hey, things happen. What got in the way?",
            },
        ],
    },
    {
        "key": "sample_check_in",
        "kind": "pair_choice",
        "prompt": "Mid-focus-session check-in I'd actually want is...",
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
                "body": "Thirty min in. You said the runsheet — on it?",
            },
        ],
    },
    {
        "key": "sample_drift_call",
        "kind": "pair_choice",
        "prompt": "When you've been off-task for a bit, the call-out I'd take well is...",
        "axis": "directness",
        "options": [
            {
                "id": "named_signal",
                "label": "Named the signal",
                "body": "I notice 12 minutes on Twitter. The work is still open.",
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
        "prompt": "After a good day, the recognition that lands is...",
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

    # --- Section 3: Calibration scales (3 axes) ---------------------------
    {
        "key": "scale_pace",
        "kind": "scale",
        "prompt": "How long should my responses run by default?",
        "axis": "pace",
        "scale_low": "Short, dense",
        "scale_high": "Longer, conversational",
    },
    {
        "key": "scale_humor",
        "kind": "scale",
        "prompt": "Humor.",
        "axis": "humor",
        "scale_low": "None — keep it clean",
        "scale_high": "Playful when it fits",
    },
    {
        "key": "scale_pushback",
        "kind": "scale",
        "prompt": "When I disagree with you, how much do I push?",
        "axis": "pushback",
        "scale_low": "Defer — you know best",
        "scale_high": "Push back when I think you're wrong",
    },

    # --- Section 4: Lifestyle stance (multi-select) -----------------------
    {
        "key": "lifestyle_topics",
        "kind": "multi_choice",
        "prompt": "Which lifestyle topics should I engage with proactively (vs. only when you raise them)?",
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

    # --- Section 5: Free-form catch-all -----------------------------------
    {
        "key": "free_form",
        "kind": "text_long",
        "prompt": "Anything else I should know about how you want this to feel? (skippable)",
        "axis": "free_form",
        "optional": True,
    },
]


# --- Synthesis prompt for v2 -------------------------------------------------

SYNTHESIS_PROMPT_V2 = """You are running the persona calibration synthesis pass.

You receive structured intake answers from the user across several question kinds:
  - text_short / text_long : free-form text
  - pair_choice            : the user picked option A or B from two sample exchanges
  - scale                  : 1..5 on a named axis with low/high anchors
  - multi_choice           : zero or more selected ids from a list

Map these to the six calibration axes the system uses:
  warmth, directness, humor, pace, failure_register, pushback_tendency.

How to read each kind:
  - pair_choice answers are the most reliable signal — they bypass self-description.
    Weight them heavily.
  - scale answers confirm or refine the pair_choice signal.
  - text answers (especially free_form) can override anything else if the user
    explicitly asked for it.

Your job: produce two markdown documents and a name choice. Output a single JSON
object with exactly these keys (no fences, no prose):

  {
    "persona_md": string,    // full PERSONA.md contents
    "memory_md":  string,    // full MEMORY.md contents
    "name":       string     // chosen persona name, or "Coach" if none chosen
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
<2-6 sentences describing the calibrated voice>

## Sample Exchanges
<4-6 short exchanges showing the calibrated voice across: routine question,
failure acknowledgment, pushback, difficult honesty, lifestyle-topic surfacing,
proactive observation. Echo the option the user chose for the failure /
check-in / drift / good-day exchanges.>

## Behavioral Anchors
<bullet list of dos and don'ts derived from the calibration>

## Lifestyle Topic Stance
<which topics are engaged proactively vs. only when raised, based on the
multi_choice answer>
```

MEMORY.md must follow this structure:

```
# About <user>

## Profession and Work
<from the occupation answer; one sentence>

## Cognitive Profile
<from the adhd_pattern answer; verbatim is fine if it's clear>

## Communication Preferences
<inferred from the calibration axes — short summary>

## Stated Values
<inferred from free_form if available; else 'not yet recorded — to be learned'>
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


# --- Back-compat exports for the old CLI/tests still importing these ---

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
