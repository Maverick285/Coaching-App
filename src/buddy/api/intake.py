"""Persona calibration intake endpoints."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from buddy.auth import require_auth
from buddy.config import get_settings
from buddy.db import get_session_factory
from buddy.llm.client import chat, chat_with_tool
from buddy.llm.models import ModelTier, resolve_model
from buddy.llm.prompts.intake import (
    INTAKE_QUESTIONS,
    SYNTHESIS_PROMPT,
    build_synthesis_user_message,
)
from buddy.llm.tools import SYNTHESIZE_PERSONA_TOOL
from buddy.memory.index import index_file
from buddy.memory.store import MemoryStore
from buddy.models import ApiUsage, IntakeSession
from buddy.schemas import (
    IntakeFinalizeRequest,
    IntakeFinalizeResponse,
    IntakeOption,
    IntakeQuestion,
    IntakeStartResponse,
    IntakeTurnRequest,
    IntakeTurnResponse,
)

router = APIRouter()


def _to_question_dto(q: dict) -> IntakeQuestion:
    """Convert the raw question-spec dict into the typed wire shape."""
    options = q.get("options")
    return IntakeQuestion(
        key=q["key"],
        kind=q["kind"],
        prompt=q["prompt"],
        axis=q.get("axis", ""),
        optional=bool(q.get("optional", False)),
        options=[IntakeOption(**o) for o in options] if options else None,
        scale_low=q.get("scale_low"),
        scale_high=q.get("scale_high"),
    )


@router.post("/intake/start", response_model=IntakeStartResponse, dependencies=[Depends(require_auth)])
async def start_intake() -> IntakeStartResponse:
    intake_id = uuid.uuid4().hex
    factory = get_session_factory()
    async with factory() as db:
        db.add(
            IntakeSession(
                id=intake_id,
                started_at=datetime.utcnow(),
                state={"step": 0},
                transcript=[],
            )
        )
        await db.commit()
    return IntakeStartResponse(
        intake_id=intake_id,
        question=_to_question_dto(INTAKE_QUESTIONS[0]),
        step=1,
        total_steps=len(INTAKE_QUESTIONS),
    )


@router.post("/intake/turn", response_model=IntakeTurnResponse, dependencies=[Depends(require_auth)])
async def intake_turn(req: IntakeTurnRequest) -> IntakeTurnResponse:
    factory = get_session_factory()
    async with factory() as db:
        sess = await db.get(IntakeSession, req.intake_id)
        if sess is None:
            raise HTTPException(404, "Intake session not found.")
        if sess.finalized_at is not None:
            raise HTTPException(400, "This intake has already been finalized.")

        step = int(sess.state.get("step", 0))
        if step >= len(INTAKE_QUESTIONS):
            raise HTTPException(400, "All questions have been answered. Call /intake/finalize.")

        q = INTAKE_QUESTIONS[step]
        # Normalise the typed answer into a uniform shape that both
        # build_synthesis_user_message_v2 (LLM input) and the test suite
        # can reason about.
        normalized_answer = _normalize_answer(q, req.answer)
        transcript = list(sess.transcript or [])
        transcript.append(
            {
                "key": q["key"],
                "kind": q["kind"],
                "axis": q.get("axis", ""),
                "question": q["prompt"],
                "options": q.get("options"),
                "scale_low": q.get("scale_low"),
                "scale_high": q.get("scale_high"),
                "answer": normalized_answer,
            }
        )
        new_step = step + 1
        sess.transcript = transcript
        sess.state = {**sess.state, "step": new_step}
        await db.commit()

    finished = new_step >= len(INTAKE_QUESTIONS)
    next_q = None if finished else _to_question_dto(INTAKE_QUESTIONS[new_step])
    return IntakeTurnResponse(
        intake_id=req.intake_id,
        question=next_q,
        step=new_step + 1 if not finished else len(INTAKE_QUESTIONS),
        total_steps=len(INTAKE_QUESTIONS),
        finished=finished,
    )


def _normalize_answer(question: dict, raw: dict) -> object:
    """Convert the client's typed payload into the canonical internal form
    that build_synthesis_user_message_v2 expects."""
    kind = question["kind"]
    if kind in ("text_short", "text_long"):
        text = (raw.get("text") or "").strip() if isinstance(raw, dict) else str(raw or "").strip()
        return text
    if kind == "pair_choice":
        chosen_id = raw.get("id") if isinstance(raw, dict) else None
        for opt in question.get("options") or []:
            if opt.get("id") == chosen_id:
                return {"id": chosen_id, "label": opt.get("label", "")}
        return {"id": chosen_id, "label": ""}
    if kind == "scale":
        try:
            value = int(raw.get("value", 3)) if isinstance(raw, dict) else int(raw)
        except (ValueError, TypeError):
            value = 3
        return max(1, min(5, value))
    if kind == "multi_choice":
        selected = raw.get("selected") if isinstance(raw, dict) else raw
        if not isinstance(selected, list):
            return []
        valid_ids = {o["id"] for o in (question.get("options") or [])}
        return [s for s in selected if s in valid_ids]
    return raw


@router.post(
    "/intake/finalize",
    response_model=IntakeFinalizeResponse,
    dependencies=[Depends(require_auth)],
)
async def intake_finalize(req: IntakeFinalizeRequest) -> IntakeFinalizeResponse:
    factory = get_session_factory()
    settings = get_settings()
    async with factory() as db:
        sess = await db.get(IntakeSession, req.intake_id)
        if sess is None:
            raise HTTPException(404, "Intake session not found.")
        transcript = list(sess.transcript or [])
        if not transcript:
            raise HTTPException(400, "No answers recorded.")

    user_payload = build_synthesis_user_message(transcript, settings.user_name)
    model = resolve_model(ModelTier.REASONING)

    # Native tool-use call. Anthropic schema-violation rate is <0.2%, so a
    # single attempt is normally enough; we still retry transient API
    # errors. If the path fails completely, fall back to deterministic
    # local synthesis so the user is never stranded mid-onboarding.
    payload: dict | None = None
    last_error: str = ""
    result = None
    for attempt in range(2):
        try:
            result = await chat_with_tool(
                model=model,
                system=SYNTHESIS_PROMPT,
                messages=[{"role": "user", "content": user_payload}],
                tool=SYNTHESIZE_PERSONA_TOOL,
                max_tokens=4096,
                temperature=0.5 if attempt == 0 else 0.2,
            )
            payload = result.tool_input
            if "persona_md" in payload and "memory_md" in payload:
                break
            last_error = "tool input missing required keys"
            payload = None
        except Exception as exc:
            last_error = f"tool call failed: {exc}"
            continue

    used_local_fallback = False
    if payload is None:
        payload = _render_local_synthesis(transcript, settings.user_name)
        used_local_fallback = True

    persona_md = payload["persona_md"].strip() + "\n"
    memory_md = payload["memory_md"].strip() + "\n"
    chosen_name = str(payload.get("name") or "").strip()

    store = MemoryStore()
    store.write("PERSONA.md", persona_md, commit_message="intake: synthesize PERSONA.md")
    store.write("MEMORY.md", memory_md, commit_message="intake: synthesize MEMORY.md")
    await index_file("PERSONA.md", store=store)
    await index_file("MEMORY.md", store=store)

    # Persist the persona name + mark onboarded.
    from buddy.services.profile import (
        KEY_PERSONA_NAME,
        mark_onboarded,
        set_pref,
    )

    factory = get_session_factory()
    async with factory() as db:
        sess = await db.get(IntakeSession, req.intake_id)
        if sess is not None:
            sess.finalized_at = datetime.utcnow()
        if chosen_name and chosen_name.lower() != "coach":
            await set_pref(db, KEY_PERSONA_NAME, chosen_name)
        await db.commit()
    await mark_onboarded()
    if not used_local_fallback and result is not None:
        async with factory() as db:
            db.add(
                ApiUsage(
                    provider="anthropic",
                    model=result.model,
                    operation="intake:synthesize",
                    tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out,
                    cost_usd=result.cost_usd,
                )
            )
            await db.commit()

    return IntakeFinalizeResponse(
        intake_id=req.intake_id,
        persona_md=persona_md,
        memory_md=memory_md,
    )


def _parse_synthesis_json(text: str) -> dict:
    """LLMs sometimes wrap JSON in code fences; strip them and parse."""
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            500,
            f"Synthesis output was not valid JSON. Got: {text[:500]!r}",
        ) from exc


# --- Deterministic synthesis fallback ---------------------------------------
# When the LLM is overloaded or hands us un-parseable JSON, we still need to
# finish onboarding with something usable. The structured intake answers are
# rich enough to render a perfectly serviceable PERSONA.md / MEMORY.md
# without an LLM call. The user can re-synthesize via Customize later.

_PAIR_TO_LABELS: dict[str, dict[str, str]] = {
    "sample_failure_register": {
        "matter_of_fact": "matter-of-fact",
        "warm_curious": "gentle and curious",
    },
    "sample_check_in": {
        "presence_only": "light, presence-only",
        "task_anchored": "task-anchored",
    },
    "sample_drift_call": {
        "named_signal": "blunt — names what's happening",
        "soft_ask": "soft — opens with a question",
    },
    "sample_good_day": {
        "score_only": "concise acknowledgment of the score",
        "felt_sense": "warmer recognition of the felt-sense",
    },
}

_WORK_LABELS = {
    "creative": "creative work and writing",
    "engineering": "engineering / building things",
    "management": "leading a team",
    "research": "research and analysis",
    "service": "helping people",
    "physical": "hands-on work",
    "school": "school and studying",
    "other": "other kinds of work",
}

_ADHD_LABELS = {
    "starting": "trouble starting things",
    "finishing": "trouble finishing things",
    "focus": "holding focus once started",
    "time_blind": "time blindness",
    "overthinking": "overthinking",
    "forgetting": "forgetting commitments",
    "impulsive": "impulse control",
    "intensity": "emotional intensity",
}

_LIFESTYLE_LABELS = {
    "sleep": "sleep",
    "exercise": "exercise",
    "nutrition": "nutrition",
    "substances": "alcohol / substances",
    "relationships": "relationships",
    "finances": "finances",
}


def _scale_label(value: int, low: str, mid: str, high: str) -> str:
    if value <= 2:
        return low
    if value == 3:
        return mid
    return high


def _render_local_synthesis(transcript: list[dict], user_name_default: str) -> dict:
    """Render PERSONA.md / MEMORY.md / name from structured answers, no LLM."""
    by_key = {turn.get("key"): turn for turn in transcript if turn.get("key")}

    name_turn = by_key.get("name", {})
    chosen_name = ""
    raw_name = name_turn.get("answer", "")
    if isinstance(raw_name, str) and raw_name.strip():
        chosen_name = raw_name.strip()
    user_label = chosen_name if chosen_name else user_name_default

    def _pair(key: str) -> tuple[str, str]:
        turn = by_key.get(key, {})
        ans = turn.get("answer") or {}
        chosen_id = ans.get("id") if isinstance(ans, dict) else ""
        label = _PAIR_TO_LABELS.get(key, {}).get(chosen_id or "", "balanced")
        return chosen_id or "", label

    failure_id, failure_label = _pair("sample_failure_register")
    checkin_id, checkin_label = _pair("sample_check_in")
    drift_id, drift_label = _pair("sample_drift_call")
    goodday_id, goodday_label = _pair("sample_good_day")

    def _scale(key: str, default: int = 3) -> int:
        turn = by_key.get(key, {})
        v = turn.get("answer", default)
        try:
            return max(1, min(5, int(v)))
        except (TypeError, ValueError):
            return default

    pace_v = _scale("scale_pace")
    humor_v = _scale("scale_humor")
    pushback_v = _scale("scale_pushback")

    pace_label = _scale_label(pace_v, "terse", "measured", "expansive")
    humor_label = _scale_label(humor_v, "none", "dry", "playful")
    pushback_label = _scale_label(
        pushback_v, "compliant", "calibrated", "contrarian"
    )

    warmth = "warm" if goodday_id == "felt_sense" else "neutral"
    directness = "blunt" if drift_id == "named_signal" else "diplomatic"
    failure_register = (
        "matter-of-fact" if failure_id == "matter_of_fact" else "gentle"
    )

    work_ids = by_key.get("work_shape", {}).get("answer") or []
    if not isinstance(work_ids, list):
        work_ids = []
    adhd_ids = by_key.get("adhd_signature", {}).get("answer") or []
    if not isinstance(adhd_ids, list):
        adhd_ids = []
    lifestyle_ids = by_key.get("lifestyle_topics", {}).get("answer") or []
    if not isinstance(lifestyle_ids, list):
        lifestyle_ids = []

    work_phrases = [_WORK_LABELS.get(i, i) for i in work_ids]
    adhd_phrases = [_ADHD_LABELS.get(i, i) for i in adhd_ids]
    lifestyle_phrases = [_LIFESTYLE_LABELS.get(i, i) for i in lifestyle_ids]

    proactive_clause = (
        "Engage proactively about: " + ", ".join(lifestyle_phrases) + "."
        if lifestyle_phrases
        else "Don't volunteer lifestyle topics unless the user raises them."
    )

    persona_md = f"""# Persona Profile

## Name
{chosen_name or "Coach"}

## Calibration Axes

### Warmth
{warmth}

### Directness
{directness}

### Humor
{humor_label}

### Pace
{pace_label}

### Failure Register
{failure_register}

### Pushback Tendency
{pushback_label}

## Free-form Guidance
You are {user_label}'s coach. Default to {pace_label} replies; lean
{warmth} but {directness}. After failures, respond {failure_label}.
On mid-task check-ins, default to {checkin_label}. When {user_label}
drifts off-task, your call-out is {drift_label}. After a good day,
your acknowledgment is {goodday_label}.

## Sample Exchanges
- Routine question — answer in 1-2 sentences, plain text, no headers.
- Failure ack — "{_PAIR_TO_LABELS['sample_failure_register'].get(failure_id, '')}" voice.
- Drift call — "{_PAIR_TO_LABELS['sample_drift_call'].get(drift_id, '')}" voice.
- Good-day ack — "{_PAIR_TO_LABELS['sample_good_day'].get(goodday_id, '')}" voice.

## Behavioral Anchors
- Don't open replies with "I" or with sycophantic openers.
- Default reply length follows the pace setting above.
- Pushback tendency: {pushback_label}.
- {proactive_clause}

## Lifestyle Topic Stance
{proactive_clause}
"""

    work_section = (
        ", ".join(work_phrases).capitalize() + "." if work_phrases else "Not specified."
    )
    adhd_section = (
        "Patterns the user identified: " + "; ".join(adhd_phrases) + "."
        if adhd_phrases
        else "Not specified."
    )
    pace_word = pace_label
    memory_md = f"""# About {user_label}

## Work
{work_section}

## ADHD Signature
{adhd_section}

## Communication Preferences
Prefers {pace_word}, {humor_label}-humor replies. Failure register: {failure_register}.
Pushback tendency: {pushback_label}.
"""

    return {
        "persona_md": persona_md,
        "memory_md": memory_md,
        "name": chosen_name or "Coach",
    }
