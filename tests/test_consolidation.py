"""Consolidation pass + dreams tiering."""

from __future__ import annotations

from datetime import date

from tests._helpers import consolidation_response, fake_chat_returning


def test_no_conversations_means_no_op(authed_client, monkeypatch):
    from buddy.memory.consolidation import run_consolidation
    import asyncio

    target = date.today()
    result = asyncio.run(run_consolidation(for_date=target))
    assert result["status"] == "no_conversations"


def test_consolidation_writes_day_summary_and_tiers_proposals(authed_client, monkeypatch):
    """Stage a fake conversation log on disk, then run consolidation."""
    from buddy.memory.consolidation import run_consolidation
    from buddy.memory.store import MemoryStore
    import asyncio

    target = date.today()
    store = MemoryStore()
    log_rel = store.conversation_log_path(target.isoformat(), "test")
    store.write(log_rel, "# log\n\nuser said: I felt stuck on the runsheet.\n")

    monkeypatch.setattr(
        "buddy.memory.consolidation.chat",
        fake_chat_returning(
            consolidation_response(
                day_summary="Worked on the runsheet; some friction.",
                auto_apply=[
                    {
                        "kind": "pattern_reinforce",
                        "target_path": "PATTERNS.md",
                        "summary": "Late-morning slumps on runsheet work",
                        "content": "## task_stalls\n- runsheet stalls around 11 AM (3 of 5 days).",
                        "rationale": "consistent across the week",
                    }
                ],
                review=[
                    {
                        "kind": "memory_add",
                        "target_path": "MEMORY.md",
                        "summary": "Add: user prefers terse responses",
                        "content": "User strongly prefers terse responses to status questions.",
                        "rationale": "stated in 3 exchanges",
                    }
                ],
            )
        ),
    )

    result = asyncio.run(run_consolidation(for_date=target))
    assert result["status"] == "ok"
    assert result["auto_applied"] == 1
    assert result["pending_review"] == 1
    assert result["summary_written"] is True

    # Day file written.
    day_md = store.read(store.day_file_path(target.isoformat()))
    assert "Worked on the runsheet" in day_md

    # Pending proposals visible via the dreams endpoint.
    dreams = authed_client.get("/memory/dreams").json()
    assert len(dreams["pending"]) == 1
    assert dreams["pending"][0]["target_path"] == "MEMORY.md"
    assert len(dreams["auto_applied_recent"]) == 1


def test_consolidation_recovers_from_invalid_json(authed_client, monkeypatch):
    """If the LLM returns junk twice, we mark the day failed but don't crash."""
    from buddy.memory.consolidation import run_consolidation
    from buddy.memory.store import MemoryStore
    import asyncio

    target = date.today()
    store = MemoryStore()
    store.write(
        store.conversation_log_path(target.isoformat(), "test"),
        "# log\n\nsome content\n",
    )

    monkeypatch.setattr(
        "buddy.memory.consolidation.chat",
        fake_chat_returning("garbage", "still garbage"),
    )
    result = asyncio.run(run_consolidation(for_date=target))
    assert result["status"] == "failed"
