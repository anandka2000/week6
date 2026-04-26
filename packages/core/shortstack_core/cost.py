"""Cost accounting.

Everything paid emits a ``CostEvent``. Per-video rollups are computed on demand.
Pricing is centralised here so we change one place when vendor rates move.

Note: prices are USD per unit, converted to cents in the helpers. Verify against
each vendor's current published rates before going to production. Tracked in TODO.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from .db import CostEvent as CostEventModel
from .db import Video
from .enums import CostKind
from .schemas import ScriptDraft


@dataclass(frozen=True)
class LLMRate:
    input_per_mtok_usd: float
    output_per_mtok_usd: float
    cache_read_per_mtok_usd: float
    cache_write_per_mtok_usd: float


# USD prices. Confirm before production.
LLM_PRICING: dict[str, LLMRate] = {
    "claude-sonnet-4-6": LLMRate(
        input_per_mtok_usd=3.0,
        output_per_mtok_usd=15.0,
        cache_read_per_mtok_usd=0.30,
        cache_write_per_mtok_usd=3.75,
    ),
    "claude-haiku-4-5": LLMRate(
        input_per_mtok_usd=1.0,
        output_per_mtok_usd=5.0,
        cache_read_per_mtok_usd=0.10,
        cache_write_per_mtok_usd=1.25,
    ),
}

# Per-character USD price for ElevenLabs Turbo v2.5 (~$0.30 per 1k chars).
TTS_PRICING: dict[str, float] = {
    "eleven_turbo_v2_5": 0.30 / 1_000.0,
}

# Per-image USD price.
IMAGE_PRICING: dict[str, float] = {
    "flux-schnell": 0.003,
    "pexels": 0.0,
}


def usd_to_cents(usd: float) -> Decimal:
    return Decimal(str(usd)) * Decimal("100")


def estimate_llm_cost_cents(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> Decimal:
    rate = LLM_PRICING[model]
    usd = (
        (input_tokens - cache_read_tokens) * rate.input_per_mtok_usd / 1_000_000
        + output_tokens * rate.output_per_mtok_usd / 1_000_000
        + cache_read_tokens * rate.cache_read_per_mtok_usd / 1_000_000
        + cache_write_tokens * rate.cache_write_per_mtok_usd / 1_000_000
    )
    return usd_to_cents(usd)


def estimate_tts_cost_cents(*, model: str, characters: int) -> Decimal:
    return usd_to_cents(TTS_PRICING[model] * characters)


def estimate_image_cost_cents(*, provider: str, n: int = 1) -> Decimal:
    return usd_to_cents(IMAGE_PRICING[provider] * n)


def estimate_video_cost_cents(
    draft: ScriptDraft,
    *,
    script_model: str = "claude-sonnet-4-6",
    tts_model: str = "eleven_turbo_v2_5",
    image_provider_for_hero: str = "flux-schnell",
    stock_hit_rate: float = 0.7,
) -> Decimal:
    """Pre-asset projection. Used to fail fast before any paid generation."""
    narration_chars = sum(len(s.narration) for s in draft.scenes)
    n_scenes = len(draft.scenes)

    flux_count = 1 + max(0, round(n_scenes * (1 - stock_hit_rate)))

    llm = estimate_llm_cost_cents(
        model=script_model,
        input_tokens=2_000,
        output_tokens=600,
        cache_read_tokens=1_500,
    )
    tts = estimate_tts_cost_cents(model=tts_model, characters=narration_chars)
    images = estimate_image_cost_cents(provider=image_provider_for_hero, n=flux_count)
    return llm + tts + images


def record_cost(
    session: Session,
    *,
    niche_id: UUID,
    kind: CostKind,
    provider: str,
    cost_cents: Decimal,
    model: str | None = None,
    units: float = 0,
    video_id: UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> CostEventModel:
    row = CostEventModel(
        video_id=video_id,
        niche_id=niche_id,
        kind=kind,
        provider=provider,
        model=model,
        units=Decimal(str(units)),
        cost_cents=cost_cents,
        meta=meta or {},
    )
    session.add(row)
    if video_id is not None:
        video = session.get(Video, video_id)
        if video is not None:
            video.cost_cents = int(Decimal(video.cost_cents) + cost_cents)
    return row


def record_llm(
    session: Session,
    *,
    niche_id: UUID,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    video_id: UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> CostEventModel:
    cost = estimate_llm_cost_cents(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )
    units = input_tokens + output_tokens
    return record_cost(
        session,
        niche_id=niche_id,
        kind=CostKind.LLM,
        provider="anthropic",
        model=model,
        cost_cents=cost,
        units=units,
        video_id=video_id,
        meta={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens,
            "cache_write_tokens": cache_write_tokens,
            **(meta or {}),
        },
    )


def record_tts(
    session: Session,
    *,
    niche_id: UUID,
    model: str,
    characters: int,
    video_id: UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> CostEventModel:
    cost = estimate_tts_cost_cents(model=model, characters=characters)
    return record_cost(
        session,
        niche_id=niche_id,
        kind=CostKind.TTS,
        provider="elevenlabs",
        model=model,
        cost_cents=cost,
        units=characters,
        video_id=video_id,
        meta=meta,
    )


def record_image(
    session: Session,
    *,
    niche_id: UUID,
    provider: str,
    n: int = 1,
    video_id: UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> CostEventModel:
    cost = estimate_image_cost_cents(provider=provider, n=n)
    return record_cost(
        session,
        niche_id=niche_id,
        kind=CostKind.IMAGE,
        provider=provider,
        cost_cents=cost,
        units=n,
        video_id=video_id,
        meta=meta,
    )


class CostCapExceeded(Exception):
    """Raised when a video's projected or actual cost exceeds the hard cap."""

    def __init__(self, *, video_id: UUID | None, cost_cents: Decimal, cap_cents: int):
        self.video_id = video_id
        self.cost_cents = cost_cents
        self.cap_cents = cap_cents
        super().__init__(
            f"video={video_id} cost={cost_cents:.2f}c exceeds hard cap {cap_cents}c"
        )


def assert_under_hard_cap(
    *, cost_cents: Decimal, cap_cents: int, video_id: UUID | None = None
) -> None:
    if cost_cents > cap_cents:
        raise CostCapExceeded(video_id=video_id, cost_cents=cost_cents, cap_cents=cap_cents)
