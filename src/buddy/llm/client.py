"""Thin async wrappers around Anthropic and OpenAI clients."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from buddy.config import get_settings
from buddy.llm.models import estimate_cost_usd, resolve_embedding_model

_anthropic: AsyncAnthropic | None = None
_openai: AsyncOpenAI | None = None


def get_anthropic() -> AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        settings = get_settings()
        _anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key or None)
    return _anthropic


def get_openai() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        settings = get_settings()
        _openai = AsyncOpenAI(api_key=settings.openai_api_key or None)
    return _openai


@dataclass
class LLMResult:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    raw: Any


async def chat(
    *,
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> LLMResult:
    """Send a multi-turn message to Anthropic and normalize the result."""
    client = get_anthropic()
    resp = await client.messages.create(
        model=model,
        system=system,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    text = ""
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            text += block.text
    tokens_in = getattr(resp.usage, "input_tokens", 0) if resp.usage else 0
    tokens_out = getattr(resp.usage, "output_tokens", 0) if resp.usage else 0
    return LLMResult(
        text=text,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=estimate_cost_usd(model, tokens_in, tokens_out),
        raw=resp,
    )


async def embed(texts: list[str]) -> tuple[list[list[float]], int, float]:
    """Embed a batch of texts. Returns (vectors, total_tokens, cost_usd)."""
    if not texts:
        return ([], 0, 0.0)
    client = get_openai()
    model = resolve_embedding_model()
    resp = await client.embeddings.create(model=model, input=texts)
    vectors = [item.embedding for item in resp.data]
    total_tokens = getattr(resp.usage, "total_tokens", 0) if resp.usage else 0
    cost = estimate_cost_usd(model, total_tokens, 0)
    return (vectors, total_tokens, cost)
