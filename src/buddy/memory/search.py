"""Hybrid retrieval: BM25 (FTS5) + vector (sqlite-vec) merged with reciprocal rank fusion."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import text

from buddy.config import get_settings
from buddy.db import get_session_factory
from buddy.llm.client import embed
from buddy.memory.index import pack_floats

RRF_K = 60  # standard reciprocal rank fusion constant


@dataclass
class Hit:
    chunk_id: int
    document_path: str
    chunk_index: int
    content: str
    score: float
    bm25_score: float | None = None
    vector_score: float | None = None
    heading: str | None = None


_FTS_SAFE_RE = re.compile(r"[^\w\s\-]")


def _sanitize_fts_query(q: str) -> str:
    # FTS5 has its own query syntax; quote terms to keep things safe.
    cleaned = _FTS_SAFE_RE.sub(" ", q)
    tokens = [t for t in cleaned.split() if t]
    if not tokens:
        return '""'
    return " ".join(f'"{t}"' for t in tokens)


async def bm25_search(query: str, limit: int) -> list[Hit]:
    factory = get_session_factory()
    fts_q = _sanitize_fts_query(query)
    async with factory() as session:
        rows = await session.execute(
            text(
                """
                SELECT
                    f.chunk_id      AS chunk_id,
                    f.document_path AS document_path,
                    f.chunk_index   AS chunk_index,
                    f.content       AS content,
                    bm25(document_chunks_fts) AS rank_score,
                    c.chunk_metadata AS chunk_metadata
                FROM document_chunks_fts f
                JOIN document_chunks c ON c.id = f.chunk_id
                WHERE document_chunks_fts MATCH :q
                ORDER BY rank_score ASC
                LIMIT :limit
                """
            ),
            {"q": fts_q, "limit": limit},
        )
        hits: list[Hit] = []
        for r in rows.mappings():
            # bm25() returns smaller-is-better. Invert to a positive score.
            hits.append(
                Hit(
                    chunk_id=int(r["chunk_id"]),
                    document_path=r["document_path"],
                    chunk_index=int(r["chunk_index"]),
                    content=r["content"],
                    score=-float(r["rank_score"]),
                    bm25_score=-float(r["rank_score"]),
                )
            )
        return hits


async def vector_search(query: str, limit: int) -> list[Hit]:
    from buddy.db import VEC_AVAILABLE

    if not get_settings().openai_api_key or not VEC_AVAILABLE:
        return []
    # An *invalid* key reaches the API and 401s. Swallow that (and any
    # other embedding/transport failure) and fall back to BM25-only —
    # bubbling a 500 out of /converse for a missing-secrets condition
    # is the wrong tradeoff. Hybrid search becomes keyword-only when
    # this happens; the user can fix the key from Customize when they
    # notice degraded retrieval.
    try:
        vectors, _, _ = await embed([query])
    except Exception as exc:  # noqa: BLE001
        from buddy.logging_setup import get_logger
        get_logger("search").warn("vector_search.embed_failed", error=str(exc)[:200])
        return []
    if not vectors:
        return []
    qvec = pack_floats(vectors[0])
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(
            text(
                """
                SELECT
                    v.chunk_id    AS chunk_id,
                    v.distance    AS distance,
                    c.document_path AS document_path,
                    c.chunk_index AS chunk_index,
                    c.content     AS content
                FROM document_chunks_vec v
                JOIN document_chunks c ON c.id = v.chunk_id
                WHERE v.embedding MATCH :q AND k = :limit
                ORDER BY v.distance ASC
                """
            ),
            {"q": qvec, "limit": limit},
        )
        hits: list[Hit] = []
        for r in rows.mappings():
            distance = float(r["distance"])
            hits.append(
                Hit(
                    chunk_id=int(r["chunk_id"]),
                    document_path=r["document_path"],
                    chunk_index=int(r["chunk_index"]),
                    content=r["content"],
                    score=-distance,
                    vector_score=-distance,
                )
            )
        return hits


def reciprocal_rank_fusion(
    *result_lists: list[Hit],
    k: int = RRF_K,
    limit: int = 10,
) -> list[Hit]:
    aggregated: dict[int, Hit] = {}
    fused_score: dict[int, float] = {}

    for results in result_lists:
        for rank, hit in enumerate(results):
            cid = hit.chunk_id
            increment = 1.0 / (k + rank + 1)
            fused_score[cid] = fused_score.get(cid, 0.0) + increment
            if cid not in aggregated:
                aggregated[cid] = hit
            else:
                # carry per-source sub-scores
                if hit.bm25_score is not None:
                    aggregated[cid].bm25_score = hit.bm25_score
                if hit.vector_score is not None:
                    aggregated[cid].vector_score = hit.vector_score

    for cid, hit in aggregated.items():
        hit.score = fused_score[cid]

    return sorted(aggregated.values(), key=lambda h: h.score, reverse=True)[:limit]


async def hybrid_search(query: str, limit: int = 8) -> list[Hit]:
    bm25 = await bm25_search(query, limit=limit * 2)
    vec = await vector_search(query, limit=limit * 2)
    if not bm25 and not vec:
        return []
    if not vec:
        return bm25[:limit]
    if not bm25:
        return vec[:limit]
    return reciprocal_rank_fusion(bm25, vec, limit=limit)
