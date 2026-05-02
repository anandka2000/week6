"""Cost-helper math. Pure functions, no DB."""

from __future__ import annotations

from decimal import Decimal

import pytest

from shortstack_core.cost import (
    estimate_image_cost_cents,
    estimate_llm_cost_cents,
    estimate_tts_cost_cents,
    estimate_video_cost_cents,
)
from shortstack_core.schemas import Scene, ScriptDraft


def _draft(narration_len: int = 50, n_scenes: int = 5) -> ScriptDraft:
    """Build a valid ScriptDraft.

    Scene 0 is the hook (duration_sec <= 3.0); the rest are 4.0s. Narration
    is a single token of ``narration_len`` characters so it counts as 1 word
    regardless of length (satisfies the ``scenes[0].narration`` ≤ 10 words rule).
    """
    scenes = [
        Scene(
            index=0,
            narration="x" * narration_len,
            on_screen_text="",
            visual_prompt="prompt",
            duration_sec=2.5,
        )
    ]
    scenes.extend(
        Scene(
            index=i,
            narration="x" * narration_len,
            on_screen_text="",
            visual_prompt="prompt",
            duration_sec=4.0,
        )
        for i in range(1, n_scenes)
    )
    total = 2.5 + 4.0 * (n_scenes - 1)
    return ScriptDraft(
        hook="ok hook",
        scenes=scenes,
        cta="follow",
        total_duration_sec=total,
        prompt_version="v1",
        model="claude-sonnet-4-6",
    )


def test_llm_cost_sonnet_basic():
    # 1k input + 500 output, no caching
    cost = estimate_llm_cost_cents(
        model="claude-sonnet-4-6",
        input_tokens=1000,
        output_tokens=500,
    )
    # 1000 * $3/Mtok = $0.003 = 0.3c, 500 * $15/Mtok = $0.0075 = 0.75c, total ~1.05c
    assert Decimal("1.0") < cost < Decimal("1.1")


def test_llm_cache_read_is_cheaper():
    """``input_tokens`` is uncached input only; cached tokens are billed at the
    cache-read rate. So a request that hit cache for everything should cost
    exactly ``cache_read_per_mtok / input_per_mtok`` of the full price -- for
    Sonnet's $3 vs $0.30 rates that's exactly 10x cheaper.
    """
    full = estimate_llm_cost_cents(
        model="claude-sonnet-4-6", input_tokens=10_000, output_tokens=0
    )
    cached = estimate_llm_cost_cents(
        model="claude-sonnet-4-6",
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=10_000,
    )
    assert cached < full
    # Sonnet input = $3/Mtok, cache-read = $0.30/Mtok -> cached is exactly 10x cheaper.
    assert cached * 10 == full


def test_haiku_cheaper_than_sonnet():
    sonnet = estimate_llm_cost_cents(
        model="claude-sonnet-4-6", input_tokens=1000, output_tokens=500
    )
    haiku = estimate_llm_cost_cents(
        model="claude-haiku-4-5", input_tokens=1000, output_tokens=500
    )
    assert haiku < sonnet


def test_tts_cost_scales_with_chars():
    a = estimate_tts_cost_cents(model="eleven_turbo_v2_5", characters=100)
    b = estimate_tts_cost_cents(model="eleven_turbo_v2_5", characters=1000)
    assert b == a * 10


def test_image_pexels_is_free():
    assert estimate_image_cost_cents(provider="pexels", n=10) == Decimal("0")


def test_image_flux_priced():
    cost = estimate_image_cost_cents(provider="flux-schnell", n=4)
    # $0.003 * 4 = $0.012 = 1.2c
    assert Decimal("1.1") < cost < Decimal("1.3")


def test_video_estimate_under_soft_cap_for_typical_script():
    # 5 scenes, ~50 chars narration each, 1 hero Flux + ~30% Flux fallback
    draft = _draft(narration_len=50, n_scenes=5)
    estimate = estimate_video_cost_cents(draft)
    # Soft cap is 75c; estimate should be well under it.
    assert estimate < Decimal("75"), f"expected < 75c, got {estimate}c"


def test_video_estimate_grows_with_narration():
    short = estimate_video_cost_cents(_draft(narration_len=10))
    long = estimate_video_cost_cents(_draft(narration_len=200))
    assert long > short


def test_unknown_model_raises():
    with pytest.raises(KeyError):
        estimate_llm_cost_cents(model="nope", input_tokens=10, output_tokens=10)
