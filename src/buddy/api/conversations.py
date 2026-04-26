"""List sessions and read full session history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from buddy.auth import require_auth
from buddy.db import get_session_factory
from buddy.models import Conversation, ConversationMessage
from buddy.schemas import (
    ConversationDetail,
    ConversationMessageOut,
    ConversationSummary,
    ConversationsResponse,
)

router = APIRouter()


@router.get(
    "/conversations",
    response_model=ConversationsResponse,
    dependencies=[Depends(require_auth)],
)
async def list_conversations(limit: int = 50) -> ConversationsResponse:
    factory = get_session_factory()
    async with factory() as db:
        rows = (
            await db.execute(
                select(Conversation).order_by(Conversation.last_message_at.desc()).limit(limit)
            )
        ).scalars().all()
        counts = dict(
            (
                await db.execute(
                    select(
                        ConversationMessage.session_id,
                        func.count(ConversationMessage.id),
                    )
                    .where(ConversationMessage.session_id.in_([r.session_id for r in rows]))
                    .group_by(ConversationMessage.session_id)
                )
            ).all()
        )
    return ConversationsResponse(
        sessions=[
            ConversationSummary(
                session_id=r.session_id,
                started_at=r.started_at,
                last_message_at=r.last_message_at,
                title=r.title,
                message_count=int(counts.get(r.session_id, 0)),
            )
            for r in rows
        ]
    )


@router.get(
    "/conversations/{session_id}",
    response_model=ConversationDetail,
    dependencies=[Depends(require_auth)],
)
async def get_conversation(session_id: str) -> ConversationDetail:
    factory = get_session_factory()
    async with factory() as db:
        convo = await db.get(Conversation, session_id)
        if convo is None:
            raise HTTPException(404, "Conversation not found.")
        msgs = (
            await db.execute(
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.created_at.asc())
            )
        ).scalars().all()
    return ConversationDetail(
        session_id=convo.session_id,
        started_at=convo.started_at,
        title=convo.title,
        messages=[
            ConversationMessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
                model_used=m.model_used,
            )
            for m in msgs
        ],
    )
