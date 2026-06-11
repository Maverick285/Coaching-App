"""Memory store: path safety, seeding, git commits."""

from __future__ import annotations

import pytest

from buddy.memory.store import MemoryPathError, MemoryStore


def test_seeding_creates_default_files():
    store = MemoryStore()
    for f in ("README.md", "MEMORY.md", "PERSONA.md", "PATTERNS.md", "DREAMS.md"):
        assert store.exists(f), f"missing seed file: {f}"


def test_path_traversal_is_refused():
    store = MemoryStore()
    with pytest.raises(MemoryPathError):
        store.resolve("../escape.md")
    with pytest.raises(MemoryPathError):
        store.resolve("/etc/passwd")


def test_write_then_read_roundtrip():
    store = MemoryStore()
    store.write("episodes/test.md", "# test\n")
    assert store.read("episodes/test.md") == "# test\n"


def test_iter_files_includes_seed_files():
    store = MemoryStore()
    paths = {f.rel_path for f in store.iter_files()}
    assert "MEMORY.md" in paths
    assert "PERSONA.md" in paths
