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
from buddy.llm.client import chat
from buddy.llm.models import ModelTier, resolve_model
from buddy.llm.prompts.intake import (
    INTAKE_QUESTIONS,
    SYNTHESIS_PROMPT,
    build_synthesis_user_message,
)
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

    # Try the synthesis call up to 3 times. Anthropic transient errors
    # (overloaded, network blips) and one-off JSON-parse failures
    # ("the model wandered out of strict JSON") are both common and both
    # recoverable with a retry. Without this, a flaky network leaves the
    # user stranded mid-onboarding.
    payload: dict | None = None
    last_error: str = ""
    result = None
    for attempt in range(3):
        try:
            result = await chat(
                model=model,
                system=SYNTHESIS_PROMPT,
                messages=[{"role": "user", "content": user_payload}],
                max_tokens=4096,
                temperature=0.5 if attempt == 0 else 0.2,
            )
        except Exception as exc:
            last_error = f"Anthropic call failed: {exc}"
            continue
        try:
            payload = _parse_synthesis_json(result.text)
            break
        except HTTPException as http_exc:
            last_error = f"Output not JSON (attempt {attempt + 1}): {http_exc.detail}"
            continue

    if payload is None:
        raise HTTPException(
            502,
            f"Synthesis failed after 3 attempts. Last error: {last_error}",
        )

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
