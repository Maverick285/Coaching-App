"""Reciprocal rank fusion invariants."""

from __future__ import annotations

from buddy.memory.search import Hit, reciprocal_rank_fusion


def _hit(cid: int, score: float, *, bm25: float | None = None, vec: float | None = None) -> Hit:
    return Hit(
        chunk_id=cid,
        document_path=f"doc{cid}.md",
        chunk_index=0,
        content=f"chunk {cid}",
        score=score,
        bm25_score=bm25,
        vector_score=vec,
    )


def test_documents_appearing_in_both_lists_outrank_those_in_one():
    bm25 = [_hit(1, 1.0, bm25=1.0), _hit(2, 0.9, bm25=0.9)]
    vec = [_hit(2, -0.1, vec=-0.1), _hit(3, -0.2, vec=-0.2)]
    fused = reciprocal_rank_fusion(bm25, vec, limit=10)
    ids_in_order = [h.chunk_id for h in fused]
    assert ids_in_order[0] == 2  # appeared in both
    assert set(ids_in_order) == {1, 2, 3}


def test_fusion_respects_limit():
    bm25 = [_hit(i, float(10 - i), bm25=float(10 - i)) for i in range(10)]
    vec = [_hit(i + 100, float(10 - i), vec=float(10 - i)) for i in range(10)]
    fused = reciprocal_rank_fusion(bm25, vec, limit=5)
    assert len(fused) == 5
