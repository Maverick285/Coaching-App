"""Assemble the per-conversation memory context.

The output is fed into the persona system prompt:

  1. Always-loaded files (MEMORY.md, PERSONA.md)
  2. Today's day file + yesterday's day file
  3. Search-retrieved chunks via hybrid_search
  4. Active patterns (high-confidence entries from PATTERNS.md plus search hits)
  5. (Recent conversation history is appended by the converse handler.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import tiktoken

from buddy.memory.schemas import ALWAYS_LOADED_FILES
from buddy.memory.search import Hit, hybrid_search
from buddy.memory.store import MemoryStore

TARGET_TOKENS = 8000
HARD_LIMIT_TOKENS = 12000

_encoder = tiktoken.get_encoding("cl100k_base")


def _count(text: str) -> int:
    return len(_encoder.encode(text))


@dataclass
class LoadedItem:
    file: str
    reason: str
    content: str
    score: float | None = None


@dataclass
class AssembledContext:
    items: list[LoadedItem] = field(default_factory=list)
    total_tokens: int = 0

    def render(self) -> str:
        sections: list[str] = []
        for item in self.items:
            sections.append(
                f"### From `{item.file}` ({item.reason})\n\n{item.content.strip()}\n"
            )
        return "\n".join(sections)

    def summary_for_response(self) -> list[dict[str, str | float | None]]:
        return [
            {"file": i.file, "reason": i.reason, "score": i.score} for i in self.items
        ]


async def assemble_context(
    *,
    user_message: str,
    today: date | None = None,
    search_limit: int = 8,
    store: MemoryStore | None = None,
) -> AssembledContext:
    store = store or MemoryStore()
    today = today or datetime.now().date()
    yesterday = today - timedelta(days=1)

    ctx = AssembledContext()

    def _add(file: str, reason: str, content: str, score: float | None = None) -> bool:
        ntok = _count(content)
        if ctx.total_tokens + ntok > HARD_LIMIT_TOKENS:
            return False
        ctx.items.append(LoadedItem(file=file, reason=reason, content=content, score=score))
        ctx.total_tokens += ntok
        return True

    # 1. Always-loaded files.
    for f in ALWAYS_LOADED_FILES:
        if store.exists(f):
            _add(f, "always loaded", store.read(f))

    # 2. Day files for today and yesterday.
    today_path = store.day_file_path(today.isoformat())
    yesterday_path = store.day_file_path(yesterday.isoformat())
    if store.exists(today_path):
        _add(today_path, "today", store.read(today_path))
    if store.exists(yesterday_path):
        _add(yesterday_path, "yesterday", store.read(yesterday_path))

    # 3. PATTERNS.md is always loaded (small and high-signal); search inside it
    #    can be done with a future refinement.
    if store.exists("PATTERNS.md"):
        _add("PATTERNS.md", "active patterns", store.read("PATTERNS.md"))

    # 4. Search-retrieved chunks. Skip files we already loaded in full.
    already_loaded = {item.file for item in ctx.items}
    if ctx.total_tokens < TARGET_TOKENS:
        hits: list[Hit] = await hybrid_search(user_message, limit=search_limit)
        for h in hits:
            if h.document_path in already_loaded:
                continue
            label = f"{h.document_path}#chunk{h.chunk_index}"
            ok = _add(h.document_path, f"search match (score={h.score:.3f})", h.content, h.score)
            if not ok:
                break

    return ctx
