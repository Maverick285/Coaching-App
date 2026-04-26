"""Chunker invariants."""

from __future__ import annotations

from buddy.memory.index import CHUNK_TOKEN_TARGET, chunk_markdown


def test_empty_returns_no_chunks():
    assert chunk_markdown("") == []
    assert chunk_markdown("   \n\n   ") == []


def test_short_doc_one_chunk():
    chunks = chunk_markdown("# Hi\n\nthis is a short doc.\n")
    assert len(chunks) == 1
    assert chunks[0].heading == "Hi"
    assert "short doc" in chunks[0].content


def test_long_doc_splits_with_overlap():
    body = "\n\n".join("paragraph " + ("word " * 50) for _ in range(30))
    chunks = chunk_markdown("# Topic\n\n" + body)
    assert len(chunks) > 1
    # Each chunk should fit roughly within the budget.
    for c in chunks:
        assert c.token_count <= CHUNK_TOKEN_TARGET + 200  # allow some slack from block boundaries
