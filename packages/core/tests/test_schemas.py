"""Pydantic schema round-trip + validation tests."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from shortstack_core.enums import AssetKind, CostKind, Platform, TrendSource, Visibility
from shortstack_core.schemas import (
    AssetRef,
    CostEvent,
    NichePersona,
    PublicationResult,
    Scene,
    ScriptDraft,
    TrendItem,
)


def _scenes(durations: list[float]) -> list[Scene]:
    return [
        Scene(
            index=i,
            narration=f"line {i}",
            on_screen_text="",
            visual_prompt=f"prompt {i}",
            duration_sec=d,
        )
        for i, d in enumerate(durations)
    ]


def test_trend_item_roundtrip():
    t = TrendItem(
        source=TrendSource.REDDIT,
        external_id="abc123",
        title="some title",
        url="https://reddit.com/r/x/abc123",
        raw={"score": 42},
        fetched_at=datetime.now(tz=timezone.utc),
    )
    again = TrendItem.model_validate_json(t.model_dump_json())
    assert again.source is TrendSource.REDDIT
    assert again.external_id == "abc123"


def test_script_hook_word_limit():
    long_hook = " ".join(["word"] * 16)
    with pytest.raises(ValidationError):
        ScriptDraft(
            hook=long_hook,
            scenes=_scenes([4, 4, 4, 4, 4]),
            cta="follow",
            total_duration_sec=20,
            prompt_version="v1",
            model="claude-sonnet-4-6",
        )


def test_script_total_duration_must_match():
    with pytest.raises(ValidationError):
        ScriptDraft(
            hook="ok",
            scenes=_scenes([4, 4, 4, 4]),  # sums to 16
            cta="follow",
            total_duration_sec=30,  # disagrees
            prompt_version="v1",
            model="claude-sonnet-4-6",
        )


def test_script_indices_must_be_contiguous():
    bad = _scenes([4, 4, 4, 4])
    bad[2] = Scene(
        index=99, narration="x", on_screen_text="", visual_prompt="x", duration_sec=4
    )
    with pytest.raises(ValidationError):
        ScriptDraft(
            hook="ok",
            scenes=bad,
            cta="follow",
            total_duration_sec=16,
            prompt_version="v1",
            model="claude-sonnet-4-6",
        )


def test_script_total_duration_cap():
    with pytest.raises(ValidationError):
        ScriptDraft(
            hook="ok",
            scenes=_scenes([6, 6, 6, 6, 6, 6, 6, 6, 6, 6]),  # 60s
            cta="follow",
            total_duration_sec=60,
            prompt_version="v1",
            model="claude-sonnet-4-6",
        )


def test_asset_ref_validates_kind():
    a = AssetRef(
        kind=AssetKind.IMAGE,
        scene_index=0,
        provider="flux",
        s3_key="videos/abc/scene_0.png",
    )
    assert a.kind is AssetKind.IMAGE


def test_cost_event_non_negative():
    with pytest.raises(ValidationError):
        CostEvent(
            niche_id=uuid4(),
            kind=CostKind.LLM,
            provider="anthropic",
            model="claude-sonnet-4-6",
            units=-1,
            cost_cents=0,
        )


def test_publication_result():
    p = PublicationResult(
        platform=Platform.YOUTUBE_SHORTS,
        external_id="dQw4w9WgXcQ",
        external_url="https://youtube.com/shorts/dQw4w9WgXcQ",
        visibility=Visibility.UNLISTED,
    )
    assert p.platform is Platform.YOUTUBE_SHORTS


def test_persona_defaults():
    p = NichePersona(brand="Trending Tech", voice_id="abc")
    assert "pattern_interrupt" in p.hook_styles
