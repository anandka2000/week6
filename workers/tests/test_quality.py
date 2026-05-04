"""Auto-approve heuristic — pure unit tests, no DB."""

from __future__ import annotations

from shortstack_core.quality import AutoApproveDecision, should_auto_approve
from shortstack_core.settings import Settings


def _settings(**overrides) -> Settings:
    """A Settings instance with defaults; pass kwargs to override."""
    base = {
        "auto_approve_min_duration_sec": 15.0,
        "auto_approve_max_duration_sec": 60.0,
        "auto_approve_min_words_per_sec": 1.0,
        "auto_approve_max_cost_cents": 200,
        "auto_approve_flop_threshold_views": 100,
        "auto_approve_flop_streak": 3,
    }
    base.update(overrides)
    return Settings(**base)


def test_passes_typical_short():
    """30s video, 60 words of captions, 50¢ cost, healthy niche → approved."""
    decision = should_auto_approve(
        duration_sec=30.0,
        caption_word_count=60,
        cost_cents=50,
        recent_video_views=[5_000, 1_200, 800, 300],
        settings=_settings(),
    )
    assert decision.approved is True
    assert decision.reasons == []


def test_rejects_too_short():
    decision = should_auto_approve(
        duration_sec=10.0,
        caption_word_count=20,
        cost_cents=30,
        recent_video_views=[],
        settings=_settings(),
    )
    assert decision.approved is False
    assert any("duration" in r and "min" in r for r in decision.reasons)


def test_rejects_too_long():
    decision = should_auto_approve(
        duration_sec=90.0,
        caption_word_count=200,
        cost_cents=50,
        recent_video_views=[],
        settings=_settings(),
    )
    assert decision.approved is False
    assert any("duration" in r and "max" in r for r in decision.reasons)


def test_rejects_thin_caption_coverage():
    """30s video with only 5 captioned words = 0.17 wps, well below 1.0."""
    decision = should_auto_approve(
        duration_sec=30.0,
        caption_word_count=5,
        cost_cents=30,
        recent_video_views=[],
        settings=_settings(),
    )
    assert decision.approved is False
    assert any("caption coverage" in r for r in decision.reasons)


def test_rejects_runaway_cost():
    decision = should_auto_approve(
        duration_sec=30.0,
        caption_word_count=60,
        cost_cents=300,  # over the 200c sanity ceiling
        recent_video_views=[],
        settings=_settings(),
    )
    assert decision.approved is False
    assert any("cost" in r and "300c" in r for r in decision.reasons)


def test_rejects_on_flop_streak():
    """3 most-recent videos all under 100 views → niche is flopping → manual."""
    decision = should_auto_approve(
        duration_sec=30.0,
        caption_word_count=60,
        cost_cents=50,
        recent_video_views=[10, 50, 80, 5_000, 1_200],  # latest 3 are flops
        settings=_settings(),
    )
    assert decision.approved is False
    assert any("flop streak" in r for r in decision.reasons)


def test_one_winner_breaks_streak():
    """A single recent winner breaks the streak."""
    decision = should_auto_approve(
        duration_sec=30.0,
        caption_word_count=60,
        cost_cents=50,
        recent_video_views=[5_000, 50, 80, 10],  # most recent is a winner
        settings=_settings(),
    )
    assert decision.approved is True


def test_short_history_does_not_trigger_streak():
    """Niche with fewer than streak-length videos is exempt from the check."""
    decision = should_auto_approve(
        duration_sec=30.0,
        caption_word_count=60,
        cost_cents=50,
        recent_video_views=[10, 5],  # only 2 videos; streak is 3
        settings=_settings(),
    )
    assert decision.approved is True


def test_empty_history_passes():
    """Brand-new niche with no published videos: streak check skipped."""
    decision = should_auto_approve(
        duration_sec=30.0,
        caption_word_count=60,
        cost_cents=50,
        recent_video_views=[],
        settings=_settings(),
    )
    assert decision.approved is True


def test_all_failures_collected_at_once():
    """A pathologically bad video reports every failed gate, not just the first."""
    decision = should_auto_approve(
        duration_sec=5.0,        # too short
        caption_word_count=1,    # thin captions
        cost_cents=500,          # runaway cost
        recent_video_views=[10, 20, 30],  # flop streak
        settings=_settings(),
    )
    assert decision.approved is False
    assert len(decision.reasons) == 4


def test_decision_is_immutable():
    """``AutoApproveDecision`` is a frozen dataclass — operator code that
    receives one cannot mutate the reason list and surprise itself."""
    import pytest

    decision = should_auto_approve(
        duration_sec=30.0,
        caption_word_count=60,
        cost_cents=50,
        recent_video_views=[],
        settings=_settings(),
    )
    with pytest.raises(Exception):
        decision.approved = False  # type: ignore[misc]
    assert isinstance(decision, AutoApproveDecision)
