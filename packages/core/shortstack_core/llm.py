"""Anthropic client wrapper. Centralises prompt caching, usage extraction, retries.

Calls return both the parsed content and a ``UsageInfo`` block so the caller
can record a CostEvent without re-shaping vendor responses.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic

from .settings import get_settings


@dataclass(frozen=True)
class UsageInfo:
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int


@dataclass(frozen=True)
class LLMResponse:
    text: str
    usage: UsageInfo


_client: Anthropic | None = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=get_settings().anthropic_api_key)
    return _client


def call_messages(
    *,
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 2048,
    cache_system: bool = True,
) -> LLMResponse:
    """Multi-turn message. ``system`` is sent with cache_control when ``cache_system``
    so reprompts re-use the cached system block. ``messages`` is the full
    conversation including the latest user follow-up.
    """

    system_block: list[dict[str, Any]] | str
    if cache_system:
        system_block = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]
    else:
        system_block = system

    msg = get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_block,
        messages=messages,
    )

    text_parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    text = "\n".join(text_parts)

    usage = UsageInfo(
        model=model,
        input_tokens=msg.usage.input_tokens,
        output_tokens=msg.usage.output_tokens,
        cache_read_tokens=getattr(msg.usage, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(msg.usage, "cache_creation_input_tokens", 0) or 0,
    )
    return LLMResponse(text=text, usage=usage)


def call(
    *,
    model: str,
    system: str,
    user: str,
    max_tokens: int = 2048,
    cache_system: bool = True,
) -> LLMResponse:
    """Single-turn convenience wrapper around :func:`call_messages`."""
    return call_messages(
        model=model,
        system=system,
        messages=[{"role": "user", "content": user}],
        max_tokens=max_tokens,
        cache_system=cache_system,
    )


_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Pull a JSON object out of an LLM response, fenced or not."""
    text = text.strip()
    m = _JSON_FENCE.search(text)
    if m:
        return json.loads(m.group(1))
    return json.loads(text)
