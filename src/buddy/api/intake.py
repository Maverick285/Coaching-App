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
    IntakeStartResponse,
    IntakeTurnRequest,
    IntakeTurnResponse,
)

router = APIRouter()


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
    first = INTAKE_QUESTIONS[0]
    return IntakeStartResponse(
        intake_id=intake_id,
        question=first["prompt"],
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
        transcript = list(sess.transcript or [])
        transcript.append(
            {
                "key": q["key"],
                "question": q["prompt"],
                "answer": req.answer.strip(),
            }
        )
        new_step = step + 1
        sess.transcript = transcript
        sess.state = {**sess.state, "step": new_step}
        await db.commit()

    finished = new_step >= len(INTAKE_QUESTIONS)
    next_q = None if finished else INTAKE_QUESTIONS[new_step]["prompt"]
    return IntakeTurnResponse(
        intake_id=req.intake_id,
        question=next_q,
        step=new_step + 1 if not finished else len(INTAKE_QUESTIONS),
        total_steps=len(INTAKE_QUESTIONS),
        finished=finished,
    )


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
    try:
        result = await chat(
            model=model,
            system=SYNTHESIS_PROMPT,
            messages=[{"role": "user", "content": user_payload}],
            max_tokens=4096,
            temperature=0.5,
        )
    except Exception as exc:
        raise HTTPException(502, f"Synthesis call failed: {exc}") from exc

    payload = _parse_synthesis_json(result.text)
    persona_md = payload["persona_md"].strip() + "\n"
    memory_md = payload["memory_md"].strip() + "\n"

    store = MemoryStore()
    store.write("PERSONA.md", persona_md, commit_message="intake: synthesize PERSONA.md")
    store.write("MEMORY.md", memory_md, commit_message="intake: synthesize MEMORY.md")
    await index_file("PERSONA.md", store=store)
    await index_file("MEMORY.md", store=store)

    factory = get_session_factory()
    async with factory() as db:
        sess = await db.get(IntakeSession, req.intake_id)
        if sess is not None:
            sess.finalized_at = datetime.utcnow()
            await db.commit()
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
