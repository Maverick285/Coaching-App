"""Typed tool schemas for Anthropic native structured outputs.

Per master spec §44: every place AI output becomes action goes through a
typed tool definition. Schema-violation rate on this path is <0.2% vs.
5-12% for prompt-engineered JSON. No regex parsing of model responses —
ever. The application validates against these schemas; if input is
invalid the call retries once with the validation error in-prompt; if it
fails again we fall back to the deterministic local renderer where one
exists, or to ask_user as a final escape hatch.
"""

from __future__ import annotations

from typing import Any


# --- Persona intake synthesis ----------------------------------------------

SYNTHESIZE_PERSONA_TOOL: dict[str, Any] = {
    "name": "synthesize_persona",
    "description": (
        "Produce the user's full PERSONA.md and MEMORY.md from their "
        "structured intake answers, plus the chosen persona name."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "persona_md": {
                "type": "string",
                "description": "Full markdown contents of PERSONA.md.",
            },
            "memory_md": {
                "type": "string",
                "description": "Full markdown contents of MEMORY.md.",
            },
            "name": {
                "type": "string",
                "description": (
                    "The persona's chosen name. 'Coach' if the user did "
                    "not provide one."
                ),
            },
        },
        "required": ["persona_md", "memory_md", "name"],
    },
}


# --- WOOP synthesis ---------------------------------------------------------

PROPOSE_WOOP_PLAN_TOOL: dict[str, Any] = {
    "name": "propose_woop_plan",
    "description": (
        "Run the WOOP planning protocol on the user's wish and return a "
        "complete structured plan: outcome, obstacles, if-then plans, "
        "first-step tasks, and a daily pace target."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "wish": {"type": "string"},
            "outcome": {
                "type": "string",
                "description": "2-4 sentences, vivid near-feel of success.",
            },
            "obstacles": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "1-3 concrete obstacles in current reality. Specific "
                    "times/contexts/failure modes. Not 'being lazy'."
                ),
            },
            "plan": {
                "type": "array",
                "items": {"type": "string"},
                "description": "1-4 if-then statements addressing obstacles.",
            },
            "suggested_intentions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "cue_type": {
                            "type": "string",
                            "enum": ["time_place", "routine", "event", "obstacle"],
                        },
                        "cue_text": {"type": "string"},
                        "response_text": {"type": "string"},
                    },
                    "required": ["cue_type", "cue_text", "response_text"],
                },
                "description": (
                    "2-4 implementation intentions; at least one with "
                    "cue_type=obstacle."
                ),
            },
            "suggested_tasks": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "3-6 first-step tasks, smallest first; each should "
                    "have an under-60-second start."
                ),
            },
            "suggested_pace_unit": {
                "type": "string",
                "description": "e.g. pages, minutes, sessions, lbs/week.",
            },
            "suggested_pace_amount": {"type": "number"},
            "suggested_pace_description": {
                "type": "string",
                "description": "1 sentence describing what par 1.0 looks like.",
            },
        },
        "required": [
            "wish",
            "outcome",
            "obstacles",
            "plan",
            "suggested_intentions",
            "suggested_tasks",
            "suggested_pace_unit",
            "suggested_pace_amount",
            "suggested_pace_description",
        ],
    },
}


# --- Goal planner -----------------------------------------------------------

PROPOSE_GOAL_PLAN_TOOL: dict[str, Any] = {
    "name": "propose_goal_plan",
    "description": (
        "Convert a one-line wish + optional deadline into a complete goal "
        "plan covering pace target, no-zero floor, intervention ceiling, "
        "milestones, first-week tasks with 60-second starters, and "
        "if-then implementation intentions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "statement": {
                "type": "string",
                "description": "Crisp restatement, ≤80 chars, the user's voice.",
            },
            "rationale": {"type": "string"},
            "user_facing_summary": {
                "type": "string",
                "description": "1-3 sentences for the wizard review screen.",
            },
            "pace_target_unit": {"type": "string"},
            "pace_target_amount": {"type": "number"},
            "pace_target_description": {"type": "string"},
            "mvp_threshold": {
                "type": "string",
                "description": "Smallest action that still counts as a 1.",
            },
            "intervention_ceiling": {
                "type": "integer",
                "minimum": 0,
                "maximum": 4,
            },
            "approach": {
                "type": "string",
                "enum": ["user_driven", "hybrid", "system_assisted"],
            },
            "priority": {"type": "integer", "minimum": 1, "maximum": 5},
            "milestones": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "statement": {"type": "string"},
                        "deadline": {"type": ["string", "null"]},
                        "pace_target_unit": {"type": "string"},
                        "pace_target_amount": {"type": "number"},
                        "mvp_threshold": {"type": "string"},
                    },
                    "required": [
                        "statement",
                        "pace_target_unit",
                        "pace_target_amount",
                        "mvp_threshold",
                    ],
                },
            },
            "first_week_tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "estimated_duration_minutes": {
                            "type": ["integer", "null"],
                        },
                        "first_60_seconds": {"type": "string"},
                        "scheduled_at": {"type": ["string", "null"]},
                    },
                    "required": ["description", "first_60_seconds"],
                },
            },
            "implementation_intentions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "cue_type": {
                            "type": "string",
                            "enum": ["time_place", "routine", "event", "obstacle"],
                        },
                        "cue_text": {"type": "string"},
                        "response_text": {"type": "string"},
                    },
                    "required": ["cue_type", "cue_text", "response_text"],
                },
            },
            "obstacles": {
                "type": "array",
                "items": {"type": "string"},
            },
            "outcome_vision": {"type": "string"},
        },
        "required": [
            "statement",
            "user_facing_summary",
            "pace_target_unit",
            "pace_target_amount",
            "mvp_threshold",
            "intervention_ceiling",
            "approach",
            "priority",
            "milestones",
            "first_week_tasks",
            "implementation_intentions",
            "obstacles",
            "outcome_vision",
        ],
    },
}


# --- Progress attribution ---------------------------------------------------

ATTRIBUTE_PROGRESS_TOOL: dict[str, Any] = {
    "name": "attribute_progress",
    "description": (
        "Map a free-form progress log line to one or more active goals "
        "with units and confidence."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "attributions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "goal_id": {"type": "integer"},
                        "units": {"type": "number"},
                        "unit_label": {"type": "string"},
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                        "rationale": {"type": "string"},
                    },
                    "required": [
                        "goal_id",
                        "units",
                        "unit_label",
                        "confidence",
                        "rationale",
                    ],
                },
            },
            "unattributed_text": {"type": "string"},
        },
        "required": ["attributions", "unattributed_text"],
    },
}


# --- Capture classification -------------------------------------------------

CLASSIFY_CAPTURE_TOOL: dict[str, Any] = {
    "name": "classify_capture",
    "description": (
        "Interpret a voice or text capture and propose 0+ concrete "
        "actions for the user to confirm."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": [
                                "log_progress",
                                "create_task",
                                "journal_entry",
                                "schedule_focus",
                                "create_goal",
                                "note",
                            ],
                        },
                        "summary": {"type": "string"},
                        "payload": {
                            "type": "object",
                            "description": "Kind-specific arguments.",
                        },
                    },
                    "required": ["kind", "summary"],
                },
            },
            "fallback_message": {"type": "string"},
        },
        "required": ["actions", "fallback_message"],
    },
}


# --- Consolidation ----------------------------------------------------------

PROPOSE_CONSOLIDATION_TOOL: dict[str, Any] = {
    "name": "propose_consolidation",
    "description": (
        "Produce the nightly consolidation output: a day summary plus "
        "tiered memory updates (auto-apply vs require-review)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "day_summary": {"type": "string"},
            "auto_apply": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string"},
                        "target_path": {"type": "string"},
                        "summary": {"type": "string"},
                        "content": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["kind", "target_path", "summary", "content"],
                },
            },
            "review": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string"},
                        "target_path": {"type": "string"},
                        "summary": {"type": "string"},
                        "content": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["kind", "target_path", "summary", "content"],
                },
            },
        },
        "required": ["day_summary", "auto_apply", "review"],
    },
}
