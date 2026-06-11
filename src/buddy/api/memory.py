"""Endpoints for inspecting, editing, searching, and exporting memory."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from buddy.auth import require_auth
from buddy.config import get_settings
from buddy.db import get_session_factory
from buddy.memory.dreams import apply_proposal_action, recent_auto_applied
from buddy.memory.index import index_file
from buddy.memory.search import hybrid_search
from buddy.memory.store import MemoryPathError, MemoryStore
from buddy.models import (
    ConversationMessage,
    IndexedDocument,
    MemoryProposal,
)
from buddy.schemas import (
    CloneInstructionsResponse,
    DreamAction,
    DreamActionResponse,
    DreamProposal,
    DreamsResponse,
    ExplainRequest,
    ExplainResponse,
    MemoryFileContent,
    MemoryFileMeta,
    MemoryFilesResponse,
    MemoryFileWrite,
    MemoryLoadedItem,
    SearchHit,
    SearchRequest,
    SearchResponse,
)

router = APIRouter()


@router.get("/memory/files", response_model=MemoryFilesResponse, dependencies=[Depends(require_auth)])
async def list_files() -> MemoryFilesResponse:
    store = MemoryStore()
    files = store.iter_files()
    factory = get_session_factory()
    async with factory() as db:
        indexed_paths = set(
            (await db.execute(select(IndexedDocument.path))).scalars().all()
        )
    return MemoryFilesResponse(
        files=[
            MemoryFileMeta(
                path=f.rel_path,
                document_type=f.document_type.value,
                bytes=f.size_bytes,
                last_modified=f.last_modified,
                indexed=f.rel_path in indexed_paths,
            )
            for f in files
        ]
    )


@router.get(
    "/memory/file/{path:path}",
    response_model=MemoryFileContent,
    dependencies=[Depends(require_auth)],
)
async def read_file(path: str) -> MemoryFileContent:
    store = MemoryStore()
    rel = unquote(path)
    try:
        if not store.exists(rel):
            raise HTTPException(404, f"Not found: {rel}")
        meta = store.stat(rel)
        return MemoryFileContent(
            path=rel,
            content=store.read(rel),
            last_modified=meta.last_modified,
        )
    except MemoryPathError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put(
    "/memory/file/{path:path}",
    response_model=MemoryFileContent,
    dependencies=[Depends(require_auth)],
)
async def write_file(path: str, body: MemoryFileWrite) -> MemoryFileContent:
    store = MemoryStore()
    rel = unquote(path)
    try:
        meta = store.write(rel, body.content, commit_message=body.commit_message)
    except MemoryPathError as exc:
        raise HTTPException(400, str(exc)) from exc
    await index_file(rel, store=store)
    return MemoryFileContent(path=rel, content=body.content, last_modified=meta.last_modified)


@router.post("/memory/search", response_model=SearchResponse, dependencies=[Depends(require_auth)])
async def search(req: SearchRequest) -> SearchResponse:
    hits = await hybrid_search(req.query, limit=req.limit)
    return SearchResponse(
        query=req.query,
        hits=[
            SearchHit(
                document_path=h.document_path,
                chunk_index=h.chunk_index,
                content=h.content if req.include_chunks else None,
                score=h.score,
                bm25_score=h.bm25_score,
                vector_score=h.vector_score,
            )
            for h in hits
        ],
    )


@router.get("/memory/dreams", response_model=DreamsResponse, dependencies=[Depends(require_auth)])
async def get_dreams() -> DreamsResponse:
    factory = get_session_factory()
    async with factory() as db:
        pending = (
            await db.execute(
                select(MemoryProposal)
                .where(MemoryProposal.status == "pending")
                .order_by(MemoryProposal.created_at.desc())
            )
        ).scalars().all()
    auto = await recent_auto_applied(limit=20)
    return DreamsResponse(
        pending=[_proposal_to_schema(p) for p in pending],
        auto_applied_recent=[_proposal_to_schema(p) for p in auto],
    )


@router.post(
    "/memory/dreams", response_model=DreamActionResponse, dependencies=[Depends(require_auth)]
)
async def act_on_dream(action: DreamAction) -> DreamActionResponse:
    return await apply_proposal_action(action)


@router.post("/memory/explain", response_model=ExplainResponse, dependencies=[Depends(require_auth)])
async def explain(req: ExplainRequest) -> ExplainResponse:
    factory = get_session_factory()
    async with factory() as db:
        msg = await db.get(ConversationMessage, req.message_id)
        if msg is None or msg.session_id != req.session_id:
            raise HTTPException(404, "Message not found in this session.")
        items = [MemoryLoadedItem(**item) for item in (msg.memory_loaded or [])]
        return ExplainResponse(
            session_id=req.session_id,
            message_id=req.message_id,
            memory_loaded=items,
            full_context=None,
        )


@router.get(
    "/memory/clone-instructions",
    response_model=CloneInstructionsResponse,
    dependencies=[Depends(require_auth)],
)
async def clone_instructions() -> CloneInstructionsResponse:
    settings = get_settings()
    remote = settings.git_remote or "(no remote configured — set BUDDY_GIT_REMOTE)"
    body = (
        "Your memory lives in a private git repository. To pull a local copy:\n\n"
        f"    git clone {remote} ~/buddy-memory\n\n"
        "After cloning, every nightly push will appear as new commits on `origin/main`.\n"
        "You can edit any file locally; to push edits back, ask your buddy admin to wire\n"
        "the inverse direction (Phase 1+ feature).\n"
    )
    return CloneInstructionsResponse(git_remote=remote, instructions=body)


def _proposal_to_schema(p: MemoryProposal) -> DreamProposal:
    return DreamProposal(
        id=p.id,
        proposal_kind=p.proposal_kind,
        target_path=p.target_path,
        summary=p.summary,
        proposed_content=p.proposed_content,
        rationale=p.rationale,
        status=p.status,
        created_at=p.created_at,
    )
