"""Build and update the search index over the markdown memory files.

The index has three pieces:

1. `indexed_documents`  — one row per .md file with a content hash.
2. `document_chunks`    — chunked text (~400 tokens with 80-token overlap).
3. `document_chunks_fts` — FTS5 virtual table for BM25 over chunk content.
4. `document_chunks_vec` — sqlite-vec vec0 table for embedding similarity.

The index is a derived artifact: if it's lost, it's rebuilt entirely from
the markdown files in seconds.
"""

from __future__ import annotations

import hashlib
import re
import struct
from dataclasses import dataclass

import tiktoken
from sqlalchemy import text

from buddy.db import get_engine, get_session_factory
from buddy.llm.client import embed
from buddy.llm.models import resolve_embedding_model
from buddy.memory.schemas import classify_path
from buddy.memory.store import MemoryStore
from buddy.models import DocumentChunk, IndexedDocument

# Embedding dimension for text-embedding-3-small.
EMBEDDING_DIM = 1536
CHUNK_TOKEN_TARGET = 400
CHUNK_TOKEN_OVERLAP = 80

_encoder = tiktoken.get_encoding("cl100k_base")


def _hash(text_: str) -> str:
    return hashlib.sha256(text_.encode("utf-8")).hexdigest()


def pack_floats(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


# ---- chunking ------------------------------------------------------------


@dataclass
class Chunk:
    index: int
    content: str
    token_count: int
    heading: str | None = None


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


def chunk_markdown(content: str) -> list[Chunk]:
    """Token-budgeted chunking that respects markdown headings as soft boundaries."""
    if not content.strip():
        return []

    # Split by top-level paragraphs first so we don't cut sentences in half awkwardly.
    blocks: list[str] = []
    cur: list[str] = []
    for line in content.splitlines(keepends=True):
        cur.append(line)
        if line.strip() == "":
            blocks.append("".join(cur))
            cur = []
    if cur:
        blocks.append("".join(cur))

    chunks: list[Chunk] = []
    buf_tokens: list[int] = []
    buf_text: list[str] = []
    current_heading: str | None = None
    chunk_index = 0

    def emit() -> None:
        nonlocal buf_tokens, buf_text, chunk_index
        if not buf_tokens:
            return
        text_ = "".join(buf_text).strip()
        if not text_:
            buf_tokens, buf_text = [], []
            return
        chunks.append(
            Chunk(
                index=chunk_index,
                content=text_,
                token_count=len(buf_tokens),
                heading=current_heading,
            )
        )
        chunk_index += 1
        # carry overlap
        if CHUNK_TOKEN_OVERLAP > 0 and len(buf_tokens) > CHUNK_TOKEN_OVERLAP:
            overlap_tokens = buf_tokens[-CHUNK_TOKEN_OVERLAP:]
            overlap_text = _encoder.decode(overlap_tokens)
            buf_tokens = list(overlap_tokens)
            buf_text = [overlap_text]
        else:
            buf_tokens, buf_text = [], []

    for block in blocks:
        m = _HEADING_RE.search(block)
        if m and m.start() == 0:
            current_heading = m.group(2).strip()
        block_tokens = _encoder.encode(block)
        if len(buf_tokens) + len(block_tokens) > CHUNK_TOKEN_TARGET and buf_tokens:
            emit()
        buf_tokens.extend(block_tokens)
        buf_text.append(block)

    emit()
    return chunks


# ---- index bootstrap ---------------------------------------------------


async def bootstrap_index_schema() -> None:
    """Create FTS5 + vec0 virtual tables (ORM tables come from Alembic / metadata).

    The vec0 table is best-effort: if the sqlite-vec extension didn't load
    (some hosts ship without loadable extensions enabled), we skip it and
    fall back to BM25-only search.
    """
    from buddy.db import VEC_AVAILABLE  # imported late so the connect-event has fired

    engine = get_engine()
    async with engine.begin() as conn:
        from buddy.db import Base

        await conn.run_sync(Base.metadata.create_all)

        await conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts
                USING fts5(
                    document_path UNINDEXED,
                    chunk_index UNINDEXED,
                    content,
                    chunk_id UNINDEXED,
                    tokenize='porter unicode61'
                );
                """
            )
        )

        try:
            await conn.execute(
                text(
                    f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_vec
                    USING vec0(
                        chunk_id INTEGER PRIMARY KEY,
                        embedding FLOAT[{EMBEDDING_DIM}]
                    );
                    """
                )
            )
        except Exception:
            # vec0 unavailable; vector search is silently disabled.
            pass


# ---- per-file index ------------------------------------------------------


async def index_file(rel_path: str, *, store: MemoryStore | None = None) -> int:
    """Re-index a single markdown file. Returns the number of chunks written."""
    store = store or MemoryStore()
    if not store.exists(rel_path):
        await _drop_file(rel_path)
        return 0

    meta = store.stat(rel_path)
    content = store.read(rel_path)
    new_hash = meta.content_hash

    from buddy.db import VEC_AVAILABLE

    factory = get_session_factory()
    async with factory() as session:
        existing = (
            await session.execute(
                text("SELECT content_hash FROM indexed_documents WHERE path = :p"),
                {"p": rel_path},
            )
        ).first()
        if existing and existing[0] == new_hash:
            return 0  # unchanged

        # Drop old chunks for this file (mirror tables included).
        await session.execute(
            text("DELETE FROM document_chunks_fts WHERE document_path = :p"),
            {"p": rel_path},
        )
        old_ids = (
            await session.execute(
                text("SELECT id FROM document_chunks WHERE document_path = :p"),
                {"p": rel_path},
            )
        ).scalars().all()
        if old_ids and VEC_AVAILABLE:
            try:
                await session.execute(
                    text(
                        "DELETE FROM document_chunks_vec WHERE chunk_id IN ("
                        + ",".join(str(int(i)) for i in old_ids)
                        + ")"
                    )
                )
            except Exception:
                pass
        await session.execute(
            text("DELETE FROM document_chunks WHERE document_path = :p"),
            {"p": rel_path},
        )
        await session.execute(
            text("DELETE FROM indexed_documents WHERE path = :p"),
            {"p": rel_path},
        )

        chunks = chunk_markdown(content)
        if not chunks:
            await session.commit()
            return 0

        doc_type = classify_path(rel_path).value
        session.add(
            IndexedDocument(
                path=rel_path,
                document_type=doc_type,
                content_hash=new_hash,
                doc_metadata={"size": meta.size_bytes},
            )
        )

        chunk_rows: list[DocumentChunk] = []
        for ch in chunks:
            row = DocumentChunk(
                document_path=rel_path,
                chunk_index=ch.index,
                content=ch.content,
                token_count=ch.token_count,
                chunk_metadata={"heading": ch.heading},
            )
            session.add(row)
            chunk_rows.append(row)
        await session.flush()

        # FTS5 mirror.
        for row in chunk_rows:
            await session.execute(
                text(
                    "INSERT INTO document_chunks_fts (document_path, chunk_index, content, chunk_id) "
                    "VALUES (:p, :i, :c, :cid)"
                ),
                {
                    "p": rel_path,
                    "i": row.chunk_index,
                    "c": row.content,
                    "cid": row.id,
                },
            )

        # Vector mirror: only if we have an OpenAI key AND the vec0 table loaded.
        from buddy.config import get_settings
        from buddy.db import VEC_AVAILABLE

        if get_settings().openai_api_key and VEC_AVAILABLE:
            try:
                vectors, _, _ = await embed([r.content for r in chunk_rows])
                for row, vec in zip(chunk_rows, vectors, strict=True):
                    await session.execute(
                        text(
                            "INSERT INTO document_chunks_vec(chunk_id, embedding) "
                            "VALUES (:cid, :v)"
                        ),
                        {"cid": row.id, "v": pack_floats(vec)},
                    )
            except Exception:
                # If embeddings fail for any reason, BM25 still works.
                pass
        await session.commit()
        return len(chunk_rows)


async def _drop_file(rel_path: str) -> None:
    from buddy.db import VEC_AVAILABLE

    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
            text("DELETE FROM document_chunks_fts WHERE document_path = :p"),
            {"p": rel_path},
        )
        old_ids = (
            await session.execute(
                text("SELECT id FROM document_chunks WHERE document_path = :p"),
                {"p": rel_path},
            )
        ).scalars().all()
        if old_ids and VEC_AVAILABLE:
            try:
                await session.execute(
                    text(
                        "DELETE FROM document_chunks_vec WHERE chunk_id IN ("
                        + ",".join(str(int(i)) for i in old_ids)
                        + ")"
                    )
                )
            except Exception:
                pass
        await session.execute(
            text("DELETE FROM document_chunks WHERE document_path = :p"),
            {"p": rel_path},
        )
        await session.execute(
            text("DELETE FROM indexed_documents WHERE path = :p"),
            {"p": rel_path},
        )
        await session.commit()


# ---- full reconciliation ----------------------------------------------


async def reconcile_index() -> dict[str, int]:
    """Walk the memory directory and bring the index into sync.

    Returns a dict of {indexed, unchanged, removed} counts.
    """
    await bootstrap_index_schema()
    store = MemoryStore()
    files = store.iter_files()
    file_paths = {f.rel_path for f in files}

    indexed = 0
    unchanged = 0
    for f in files:
        n = await index_file(f.rel_path, store=store)
        if n == 0:
            unchanged += 1
        else:
            indexed += 1

    removed = 0
    factory = get_session_factory()
    async with factory() as session:
        rows = (
            await session.execute(text("SELECT path FROM indexed_documents"))
        ).scalars().all()
        for path in rows:
            if path not in file_paths:
                await _drop_file(path)
                removed += 1

    _ = resolve_embedding_model()  # touch resolver so it caches
    return {"indexed": indexed, "unchanged": unchanged, "removed": removed}
