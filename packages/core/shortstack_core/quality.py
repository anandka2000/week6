"""Auto-approve quality heuristic.

Phase 9 gate: after ``render_video`` produces an mp4, the worker calls
``should_auto_approve(...)`` and routes the video to ``APPROVED`` (skip
the human review queue) or ``PENDING_REVIEW`` (default v0 behaviour).

The decision is intentionally pure: callers pass plain values, the
helper returns a ``AutoApproveDecision`` with reasons. This keeps it
fully unit-testable without DB or storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .settings import Settings, get_settings


@dataclass(frozen=True)
class AutoApproveDecision:
    approved: bool
    reasons: list[str] = field(default_factory=list)
    """Human-readable reasons.

    When ``approved`` is True, reasons is empty (or contains
    ``"all checks passed"`` as a single sentinel).
    When ``approved`` is False, reasons lists every failed check —
    operator dashboards / logs surface this as the held-for-review cause.
    """


def should_auto_approve(
    *,
    duration_sec: float,
    caption_word_count: int,
    cost_cents: int,
    recent_video_views: list[int],
    settings: Settings | None = None,
) -> AutoApproveDecision:
    """Apply every gate. ``approved`` is True iff none fired.

    Inputs (all callers compute these and hand them in):

    - ``duration_sec``: from the render-service response (or
      ``draft.total_duration_sec`` as a fallback).
    - ``caption_word_count``: ``len(CaptionsDoc.words)`` for the rendered
      video.
    - ``cost_cents``: ``Video.cost_cents`` after the render finishes.
    - ``recent_video_views``: most-recent-first list of latest-snapshot
      ``views`` for prior published videos in this niche. Empty list is
      fine for new niches (the flop-streak check is skipped).
    """
    s = settings or get_settings()
    reasons: list[str] = []

    # 1. Duration in the right range.
    if duration_sec < s.auto_approve_min_duration_sec:
        reasons.append(
            f"duration {duration_sec:.1f}s < min {s.auto_approve_min_duration_sec}s"
        )
    elif duration_sec > s.auto_approve_max_duration_sec:
        reasons.append(
            f"duration {duration_sec:.1f}s > max {s.auto_approve_max_duration_sec}s"
        )

    # 2. Caption coverage (proxy for audio quality + caption sync).
    if duration_sec > 0:
        wps = caption_word_count / duration_sec
        if wps < s.auto_approve_min_words_per_sec:
            reasons.append(
                f"caption coverage {wps:.2f} words/sec "
                f"< min {s.auto_approve_min_words_per_sec}"
            )

    # 3. Cost sanity check. Per-video hard cap is enforced upstream; this
    #    catches anything that slipped through (e.g. a future rolling-cap
    #    rounding bug).
    if cost_cents > s.auto_approve_max_cost_cents:
        reasons.append(
            f"cost {cost_cents}c > sanity ceiling {s.auto_approve_max_cost_cents}c"
        )

    # 4. Niche flop streak. If the last N published videos all underperformed,
    #    drop back to manual review until the operator either rejects them or
    #    publishes a winner.
    needed = s.auto_approve_flop_streak
    if len(recent_video_views) >= needed:
        recent_n = recent_video_views[:needed]
        if all(v < s.auto_approve_flop_threshold_views for v in recent_n):
            reasons.append(
                f"niche on flop streak: last {needed} videos all < "
                f"{s.auto_approve_flop_threshold_views} views"
            )

    return AutoApproveDecision(approved=not reasons, reasons=reasons)
