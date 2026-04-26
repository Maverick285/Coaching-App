"""Progress-log endpoints (structured + free-form attribution)."""

from __future__ import annotations

import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from buddy.auth import require_auth
from buddy.db import get_session_factory
from buddy.llm.client import chat
from buddy.llm.models import ModelTier, resolve_model
from buddy.llm.prompts.planning import (
    PROGRESS_ATTRIBUTION_SYSTEM,
    build_attribution_user_message,
)
from buddy.models import ApiUsage, Goal, ProgressLog
from buddy.schemas_phase2 import (
    AttributedProgress,
    ProgressFreeForm,
    ProgressFreeFormResponse,
    ProgressLogCreate,
    ProgressLogOut,
)

router = APIRouter()


def _to_out(p: ProgressLog) -> ProgressLogOut:
    return ProgressLogOut.model_validate(
        {
            "id": p.id,
            "goal_id": p.goal_id,
            "recorded_at": p.recorded_at,
            "raw_text": p.raw_text,
            "attributed_units": p.attributed_units,
            "unit_label": p.unit_label,
            "source": p.source,
            "confidence": p.confidence,
            "note": p.note,
        }
    )


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    return cleaned


@router.post(
    "/progress/log",
    response_model=ProgressLogOut,
    dependencies=[Depends(require_auth)],
)
async def log_progress(req: ProgressLogCreate) -> ProgressLogOut:
    factory = get_session_factory()
    async with factory() as db:
        goal = await db.get(Goal, req.goal_id)
        if goal is None:
            raise HTTPException(404, f"Goal {req.goal_id} not found.")
        log = ProgressLog(
            goal_id=req.goal_id,
            raw_text=req.raw_text,
            attributed_units=req.attributed_units,
            unit_label=req.unit_label or goal.pace_target_unit,
            source=req.source,
            confidence=1.0,
            note=req.note,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
    return _to_out(log)


@router.post(
    "/progress/freeform",
    response_model=ProgressFreeFormResponse,
    dependencies=[Depends(require_auth)],
)
async def log_progress_freeform(req: ProgressFreeForm) -> ProgressFreeFormResponse:
    """Take free-form text, ask the fast LLM to attribute it to active goals,
    then write the corresponding ProgressLog rows.
    """
    factory = get_session_factory()
    async with factory() as db:
        goals = (
            await db.execute(
                select(Goal).where(Goal.state == "active").order_by(Goal.priority.desc())
            )
        ).scalars().all()

    if not goals:
        return ProgressFreeFormResponse(
            attributions=[], logged=[], unattributed_text=req.text
        )

    payload = [
        {
            "goal_id": g.id,
            "statement": g.statement,
            "pace_target_unit": g.pace_target_unit,
            "pace_target_amount": g.pace_target_amount,
        }
        for g in goals
    ]
    user_msg = build_attribution_user_message(req.text, payload)
    model = resolve_model(ModelTier.FAST)

    try:
        result = await chat(
            model=model,
            system=PROGRESS_ATTRIBUTION_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=1024,
            temperature=0.1,
        )
    except Exception as exc:
        raise HTTPException(502, f"Attribution failed: {exc}") from exc

    try:
        out = json.loads(_strip_fences(result.text))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            502, f"Attribution output not JSON: {result.text[:300]!r}"
        ) from exc

    attributions: list[AttributedProgress] = []
    for item in out.get("attributions") or []:
        attributions.append(
            AttributedProgress(
                goal_id=int(item["goal_id"]),
                units=float(item.get("units") or 0.0),
                unit_label=str(item.get("unit_label") or ""),
                confidence=float(item.get("confidence") or 0.0),
                rationale=str(item.get("rationale") or ""),
            )
        )

    factory = get_session_factory()
    written: list[ProgressLogOut] = []
    async with factory() as db:
        valid_ids = {g.id for g in goals}
        for a in attributions:
            if a.goal_id not in valid_ids or a.units <= 0:
                continue
            row = ProgressLog(
                goal_id=a.goal_id,
                raw_text=req.text,
                attributed_units=a.units,
                unit_label=a.unit_label,
                source=req.source,
                confidence=a.confidence,
                note=a.rationale,
            )
            db.add(row)
            await db.flush()
            written.append(_to_out(row))
        db.add(
            ApiUsage(
                provider="anthropic",
                model=result.model,
                operation="progress_attribution",
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=result.cost_usd,
            )
        )
        await db.commit()

    return ProgressFreeFormResponse(
        attributions=attributions,
        logged=written,
        unattributed_text=str(out.get("unattributed_text") or ""),
    )


@router.get(
    "/progress/by-goal/{goal_id}",
    dependencies=[Depends(require_auth)],
)
async def list_progress(goal_id: int, limit: int = 50) -> dict:
    factory = get_session_factory()
    async with factory() as db:
        rows = (
            await db.execute(
                select(ProgressLog)
                .where(ProgressLog.goal_id == goal_id)
                .order_by(ProgressLog.recorded_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    return {"logs": [_to_out(r).model_dump(mode="json") for r in rows]}
