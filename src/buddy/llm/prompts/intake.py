"""Persona calibration intake — questions and synthesis prompts.

The intake is a real conversation, not a form. It runs once at onboarding,
addresses the user as "Coach" (or whatever default name) until the user
chooses one, and produces both PERSONA.md and the initial MEMORY.md.
"""

from __future__ import annotations

INTAKE_QUESTIONS: list[dict[str, str]] = [
    {
        "key": "name",
        "prompt": (
            "Welcome. Before anything else: what should I be called? "
            "Most people pick a real first name; some go with something more abstract. "
            "If you're not sure, we can stay with \"Coach\" for now and you can rename me later."
        ),
    },
    {
        "key": "reference_points",
        "prompt": (
            "Describe a person — real or fictional — whose communication style you'd want from me. "
            "What about them works for you? And what would you specifically not want me to do?"
        ),
    },
    {
        "key": "failure_response",
        "prompt": (
            "When you mess up — miss a commitment, blow off a session, fall off track — "
            "what response would make you feel like getting back on the horse? And what response would make you want to throw the phone?"
        ),
    },
    {
        "key": "praise_tolerance",
        "prompt": (
            "Two extremes: (a) genuine recognition fuels you, (b) any praise feels patronizing. Where do you actually sit?"
        ),
    },
    {
        "key": "humor",
        "prompt": (
            "Humor and lightness: do you want fun, neutral, or all-business? Dry, playful, or none?"
        ),
    },
    {
        "key": "disagreement",
        "prompt": (
            "How comfortable are you with me telling you no, or pushing back? "
            "What feels like appropriate pushback vs. annoying contrarianism?"
        ),
    },
    {
        "key": "length",
        "prompt": (
            "Length and density: short dense exchanges, or fuller conversational ones? Both at different times?"
        ),
    },
    {
        "key": "lifestyle_topics",
        "prompt": (
            "Which lifestyle topics — sleep, exercise, nutrition, substances, anything else — do you want me to engage with proactively, "
            "and which do you want me to leave alone unless you raise them?"
        ),
    },
    {
        "key": "identity",
        "prompt": (
            "Tell me the basics that should live in MEMORY.md: profession and work context, "
            "ADHD profile (subtype if you know it, what the symptoms look like for you), "
            "key relationships, location and timezone, stated values, and the high-level goals on your mind right now."
        ),
    },
    {
        "key": "free_form",
        "prompt": (
            "Anything else I should know? Anything you want to say about how this should feel, what you're hoping for, what you're worried about?"
        ),
    },
]


SYNTHESIS_PROMPT = """You are running the persona calibration synthesis pass.

You will be given the full transcript of an intake conversation between the user and a coaching companion. Your job is to produce two markdown documents:

1. `PERSONA.md` — a calibrated persona profile.
2. `MEMORY.md` — the initial identity layer.

Use the user's actual answers, not generic templates. If an answer is vague, infer conservatively rather than inventing detail. Where the user explicitly said something, quote or closely paraphrase rather than rewriting in your own voice.

Output a single JSON object with exactly these keys:

  - "persona_md": string (the full PERSONA.md contents)
  - "memory_md":  string (the full MEMORY.md contents)
  - "name":       string (the persona's chosen name, or "Coach" if none was chosen)

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
<2-6 sentences in the user's words about what they want from this companion>

## Sample Exchanges
<4-6 short exchanges in the calibrated voice — routine question, failure acknowledgment, pushback, difficult honesty, lifestyle-topic surfacing, proactive observation>

## Behavioral Anchors
<bullet list of dos and don'ts derived from the calibration>

## Lifestyle Topic Stance
<which topics are engaged proactively vs. only when raised>
```

MEMORY.md must follow this structure:

```
# About <user>

## Profession and Work
...

## Cognitive Profile
...

## Relationships
...

## Location and Timezone
...

## Stated Values
...

## Communication Preferences
...

## Current High-level Goals
...
```

Be concrete. Avoid fluff. The user is high-IQ and will read this carefully.
"""


def build_synthesis_user_message(transcript: list[dict[str, str]], user_name: str) -> str:
    parts = [
        f"User name: {user_name}",
        "",
        "Transcript (each turn is a question and the user's answer):",
        "",
    ]
    for turn in transcript:
        parts.append(f"### {turn['key']}")
        parts.append(f"Q: {turn['question']}")
        parts.append(f"A: {turn['answer']}")
        parts.append("")
    return "\n".join(parts)
