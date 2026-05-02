"""Analytics task — pure-helper tests. Full DB / S3 / Sonnet paths deferred."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from shortstack_worker.tasks.analytics import _video_summary


def _video_mock(cost_cents: int = 100):
    v = MagicMock()
    v.id = uuid4()
    v.cost_cents = cost_cents
    return v


def _script_mock(hook: str = "ok", cta: str = "follow", on_screen_text: str = "STOP"):
    s = MagicMock()
    s.draft_json = {
        "hook": hook,
        "cta": cta,
        "scenes": [
            {"index": 0, "narration": "Stop", "on_screen_text": on_screen_text, "duration_sec": 2.5},
            {"index": 1, "narration": "Now this", "on_screen_text": "", "duration_sec": 4.0},
        ],
    }
    return s


def _snap_mock(views: int = 1000, likes: int = 50):
    m = MagicMock()
    m.views = views
    m.likes = likes
    return m


def test_video_summary_includes_views_per_cent():
    summary = _video_summary(
        _video_mock(cost_cents=50),
        _script_mock(),
        _snap_mock(views=500),
        ext_id="ext-abc",
    )
    assert summary["views"] == 500
    assert summary["cost_cents"] == 50
    assert summary["views_per_cent"] == 10.0  # 500 / 50


def test_video_summary_zero_cost_is_safe():
    """Margin proxy: zero cost is treated as 1 cent so we don't div-by-zero."""
    summary = _video_summary(
        _video_mock(cost_cents=0),
        _script_mock(),
        _snap_mock(views=100),
        ext_id="x",
    )
    assert summary["views_per_cent"] == 100.0  # 100 / max(0, 1) = 100


def test_video_summary_includes_hook_cta_and_external_id():
    summary = _video_summary(
        _video_mock(),
        _script_mock(hook="Stop scrolling.", cta="Follow."),
        _snap_mock(),
        ext_id="ext-xyz",
    )
    assert summary["hook"] == "Stop scrolling."
    assert summary["cta"] == "Follow."
    assert summary["external_id"] == "ext-xyz"
    # Scene topics use on_screen_text first, then narration
    assert summary["scene_topics"][0] == "STOP"
    assert summary["scene_topics"][1] == "Now this"


def test_tasks_registered():
    from shortstack_worker.tasks.analytics import (
        nightly_catchup,
        snapshot_metrics,
        weekly_learnings,
        weekly_learnings_all,
    )

    assert snapshot_metrics.name == "shortstack_worker.tasks.analytics.snapshot_metrics"
    assert nightly_catchup.name == "shortstack_worker.tasks.analytics.nightly_catchup"
    assert weekly_learnings.name == "shortstack_worker.tasks.analytics.weekly_learnings"
    assert weekly_learnings_all.name == "shortstack_worker.tasks.analytics.weekly_learnings_all"


def test_learnings_key_format():
    from shortstack_core.prompts import learnings_key

    nid = uuid4()
    assert learnings_key(nid) == f"niches/{nid}/learnings_v1.md"
    assert learnings_key("ai-productivity") == "niches/ai-productivity/learnings_v1.md"
