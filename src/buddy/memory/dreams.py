"""Auto-apply / require-review tiering for memory proposals.

This module owns:
  - The classification of a proposal as auto-apply vs. review.
  - Persistence of proposals to the DB.
  - The DREAMS.md mirror file (human-readable surface).
  - The action endpoint behavior (approve / reject / edit).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from buddy.db import get_session_factory
from buddy.memory.index import index_file
from buddy.memory.store import MemoryStore
from buddy.models import MemoryProposal
from buddy.schemas import DreamAction, DreamActionResponse

AUTO_APPLY_KINDS: frozenset[str] = frozenset(
    {"pattern_reinforce", "pattern_weaken", "pattern_new_high_conf"}
)
REVIEW_KINDS: frozenset[str] = frozenset(
    {
        "memory_add",
        "memory_modify",
        "pattern_new_low_conf",
        "episode_promote",
        "persona_calibration",
    }
)


def classify_kind(kind: str) -> str:
    if kind in AUTO_APPLY_KINDS:
        return "auto_apply"
    if kind in REVIEW_KINDS:
        return "review"
    return "review"  # be safe by default


async def stage_proposals(
    *,
    auto_apply_items: list[dict[str, Any]],
    review_items: list[dict[str, Any]],
) -> dict[str, int]:
    """Persist all proposals; auto-apply ones are applied immediately."""
    factory = get_session_factory()
    store = MemoryStore()
    auto_count = 0
    review_count = 0

    async with factory() as db:
        for item in auto_apply_items:
            proposal = MemoryProposal(
                id=uuid.uuid4().hex,
                proposal_kind=item["kind"],
                target_path=item["target_path"],
                summary=item["summary"],
                proposed_content=item["content"],
                rationale=item.get("rationale", ""),
                status="auto_applied",
                decided_at=datetime.utcnow(),
                proposal_metadata={"auto": True},
            )
            db.add(proposal)
            _apply_to_disk(store, proposal)
            auto_count += 1

        for item in review_items:
            db.add(
                MemoryProposal(
                    id=uuid.uuid4().hex,
                    proposal_kind=item["kind"],
                    target_path=item["target_path"],
                    summary=item["summary"],
                    proposed_content=item["content"],
                    rationale=item.get("rationale", ""),
                    status="pending",
                )
            )
            review_count += 1

        await db.commit()

    # Re-index any disk files that were touched.
    if auto_count:
        for item in auto_apply_items:
            try:
                await index_file(item["target_path"], store=store)
            except Exception:
                pass
        await _rewrite_dreams_md(store)

    if review_count:
        await _rewrite_dreams_md(store)
        await index_file("DREAMS.md", store=store)

    return {"auto_applied": auto_count, "pending_review": review_count}


def _apply_to_disk(store: MemoryStore, proposal: MemoryProposal) -> None:
    """Write the proposal content into its target file.

    For PATTERNS.md, the content is appended (with a separator).
    For new files (episodes), the content is written wholesale.
    For MEMORY.md / PERSONA.md, this is review-only, never auto-applied.
    """
    target = proposal.target_path
    if target == "PATTERNS.md":
        if not store.exists(target):
            store.write(
                target,
                "# Patterns\n\n",
                commit_message="dreams: bootstrap PATTERNS.md",
            )
        snippet = (
            f"\n<!-- proposal {proposal.id} ({proposal.proposal_kind}) -->\n"
            f"{proposal.proposed_content.strip()}\n"
        )
        store.append(target, snippet, commit_message=f"dreams: {proposal.proposal_kind} -> {target}")
        return
    # Episodes and other new files: write wholesale.
    if target.startswith("episodes/") or target.startswith("days/"):
        store.write(
            target,
            proposal.proposed_content,
            commit_message=f"dreams: {proposal.proposal_kind} -> {target}",
        )
        return
    # MEMORY.md / PERSONA.md should never reach here under auto-apply.
    # If they do, write defensively rather than silently dropping.
    store.write(
        target,
        proposal.proposed_content,
        commit_message=f"dreams (auto): {proposal.proposal_kind} -> {target}",
    )


async def apply_proposal_action(action: DreamAction) -> DreamActionResponse:
    factory = get_session_factory()
    store = MemoryStore()
    async with factory() as db:
        proposal = await db.get(MemoryProposal, action.proposal_id)
        if proposal is None:
            raise HTTPException(404, "Proposal not found.")
        if proposal.status != "pending":
            raise HTTPException(
                400, f"Proposal is already {proposal.status} and cannot be acted on."
            )

        if action.action == "reject":
            proposal.status = "rejected"
            proposal.decided_at = datetime.utcnow()
            await db.commit()
            await _rewrite_dreams_md(store)
            await index_file("DREAMS.md", store=store)
            return DreamActionResponse(
                proposal_id=proposal.id, new_status="rejected", applied_path=None
            )

        if action.action == "edit":
            if action.edited_content is None:
                raise HTTPException(400, "edit action requires edited_content.")
            proposal.proposed_content = action.edited_content
            await db.commit()
            await _rewrite_dreams_md(store)
            await index_file("DREAMS.md", store=store)
            return DreamActionResponse(
                proposal_id=proposal.id, new_status="pending", applied_path=None
            )

        # Approve.
        _apply_to_disk(store, proposal)
        proposal.status = "approved"
        proposal.decided_at = datetime.utcnow()
        await db.commit()

    # Re-index outside the DB session.
    try:
        await index_file(proposal.target_path, store=store)
    except Exception:
        pass
    await _rewrite_dreams_md(store)
    await index_file("DREAMS.md", store=store)
    return DreamActionResponse(
        proposal_id=proposal.id,
        new_status="approved",
        applied_path=proposal.target_path,
    )


async def recent_auto_applied(limit: int = 20) -> list[MemoryProposal]:
    factory = get_session_factory()
    async with factory() as db:
        rows = (
            await db.execute(
                select(MemoryProposal)
                .where(MemoryProposal.status == "auto_applied")
                .order_by(MemoryProposal.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    return list(rows)


async def _rewrite_dreams_md(store: MemoryStore) -> None:
    factory = get_session_factory()
    async with factory() as db:
        pending = (
            await db.execute(
                select(MemoryProposal)
                .where(MemoryProposal.status == "pending")
                .order_by(MemoryProposal.created_at.desc())
            )
        ).scalars().all()
        recent = (
            await db.execute(
                select(MemoryProposal)
                .where(MemoryProposal.status == "auto_applied")
                .order_by(MemoryProposal.created_at.desc())
                .limit(20)
            )
        ).scalars().all()

    parts: list[str] = ["# Dreams", ""]
    parts.append("## REQUIRES REVIEW")
    parts.append("")
    if not pending:
        parts.append("_(none)_")
    else:
        for p in pending:
            parts.append(f"### Proposed: {p.summary} (`{p.target_path}`)")
            parts.append(f"- Kind: `{p.proposal_kind}`")
            if p.rationale:
                parts.append(f"- Rationale: {p.rationale}")
            parts.append(f"- Proposal ID: `{p.id}`")
            parts.append("")
            parts.append("```markdown")
            parts.append(p.proposed_content.rstrip())
            parts.append("```")
            parts.append("")

    parts.append("## AUTO-APPLIED (for your awareness)")
    parts.append("")
    if not recent:
        parts.append("_(none yet)_")
    else:
        for p in recent:
            applied = p.decided_at.isoformat() if p.decided_at else "?"
            parts.append(
                f"- **{p.summary}** — `{p.target_path}` ({p.proposal_kind}) at {applied}"
            )

    body = "\n".join(parts) + "\n"
    store.write("DREAMS.md", body, commit_message="dreams: refresh DREAMS.md")
