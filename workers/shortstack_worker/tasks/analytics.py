"""Phase 6 analytics: per-publication metric snapshots + weekly learnings synthesis.

  snapshot_metrics(publication_id)       fetch latest stats from YouTube,
                                         insert a MetricSnapshot row.
                                         Scheduled at t+24h, t+72h, t+7d
                                         when publish_video succeeds, plus a
                                         beat-driven nightly catch-up for
                                         anything missed.

  nightly_catchup()                       beat-fired (02:00 UTC). Re-snapshots
                                          publications whose latest metric is
                                          older than 24h (or never snapshotted).

  weekly_learnings(niche_id)              read top + bottom decile videos by
                                          views-per-cent-spent. Sonnet
                                          synthesises a learnings markdown,
                                          uploaded to
                                          ``niches/{niche_id}/learnings_v1.md``.
                                          The script-gen system prompt loads
                                          this on the next run.

  weekly_learnings_all()                  beat-fired (Sunday 02:00 UTC).
                                          Fans out weekly_learnings per niche.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import desc, func, select

from shortstack_core.cost import record_llm
from shortstack_core.db import (
    MetricSnapshot,
    Niche,
    Publication,
    Script,
    Video,
    session_scope,
)
from shortstack_core.enums import Platform
from shortstack_core.llm import call as llm_call
from shortstack_core.prompts import learnings_key, load_prompt
from shortstack_core.storage import upload_bytes

from ..celery_app import app  # noqa: F401  (ensures app is registered)
from ..sources.youtube_analytics import fetch_video_stats

log = get_task_logger(__name__)

LEARNINGS_PROMPT_VERSION = "learnings_v1"
LEARNINGS_MODEL = "claude-sonnet-4-6"
MIN_VIDEOS_FOR_LEARNINGS = 6
DECILE_FLOOR = 3  # always include at least 3 videos in each tail


@shared_task(
    name="shortstack_worker.tasks.analytics.snapshot_metrics",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
)
def snapshot_metrics(publication_id: str) -> dict[str, Any]:
    pub_uuid = UUID(publication_id)

    with session_scope() as s:
        publication = s.get(Publication, pub_uuid)
        if publication is None:
            raise ValueError(f"publication {publication_id} not found")
        platform = publication.platform
        external_id = publication.external_id

    if platform != Platform.YOUTUBE_SHORTS:
        log.info(
            "snapshot_metrics.skip_platform",
            extra={"publication_id": publication_id, "platform": platform.value},
        )
        return {
            "publication_id": publication_id,
            "platform": platform.value,
            "skipped": True,
            "reason": "platform not yet supported by analytics",
        }

    stats = fetch_video_stats(external_id)
    if stats is None:
        log.warning(
            "snapshot_metrics.video_not_found",
            extra={"publication_id": publication_id, "external_id": external_id},
        )
        return {
            "publication_id": publication_id,
            "external_id": external_id,
            "skipped": True,
            "reason": "video not found on YouTube",
        }

    with session_scope() as s:
        snap = MetricSnapshot(
            publication_id=pub_uuid,
            views=stats.views,
            avg_view_duration_sec=Decimal("0"),  # Analytics API not wired yet
            retention_curve={},
            ctr=None,
            likes=stats.likes,
            comments=stats.comments,
            shares=0,
        )
        s.add(snap)
        s.flush()
        snap_id = snap.id

    log.info(
        "snapshot_metrics.done",
        extra={
            "publication_id": publication_id,
            "snapshot_id": snap_id,
            "views": stats.views,
            "likes": stats.likes,
        },
    )
    return {
        "publication_id": publication_id,
        "snapshot_id": snap_id,
        "views": stats.views,
        "likes": stats.likes,
        "comments": stats.comments,
    }


@shared_task(name="shortstack_worker.tasks.analytics.nightly_catchup", acks_late=True)
def nightly_catchup() -> dict[str, Any]:
    """Snapshot any publication whose latest metric is older than 24h."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)

    with session_scope() as s:
        latest_subq = (
            select(
                MetricSnapshot.publication_id,
                func.max(MetricSnapshot.captured_at).label("latest"),
            )
            .group_by(MetricSnapshot.publication_id)
            .subquery()
        )
        stmt = (
            select(Publication.id)
            .outerjoin(latest_subq, Publication.id == latest_subq.c.publication_id)
            .where(
                (latest_subq.c.latest.is_(None)) | (latest_subq.c.latest < cutoff)
            )
        )
        stale = [str(pid) for pid in s.execute(stmt).scalars()]

    for pid in stale:
        snapshot_metrics.apply_async(args=[pid])

    log.info("analytics.nightly_catchup", extra={"queued": len(stale)})
    return {"queued": len(stale), "publication_ids": stale}


def _video_summary(video: Video, script: Script, snap: MetricSnapshot, ext_id: str) -> dict[str, Any]:
    cost_cents = max(int(video.cost_cents), 1)  # avoid div-by-zero
    draft = script.draft_json or {}
    return {
        "video_id": str(video.id),
        "external_id": ext_id,
        "hook": draft.get("hook", ""),
        "cta": draft.get("cta", ""),
        "scene_topics": [
            (s.get("on_screen_text") or s.get("narration", ""))[:120]
            for s in (draft.get("scenes") or [])
        ],
        "views": snap.views,
        "likes": snap.likes,
        "cost_cents": int(video.cost_cents),
        "views_per_cent": round(snap.views / cost_cents, 2),
    }


@shared_task(
    name="shortstack_worker.tasks.analytics.weekly_learnings",
    acks_late=True,
)
def weekly_learnings(niche_id: str) -> dict[str, Any]:
    niche_uuid = UUID(niche_id)

    with session_scope() as s:
        niche = s.get(Niche, niche_uuid)
        if niche is None:
            raise ValueError(f"niche {niche_id} not found")
        niche_slug = niche.slug

        latest_subq = (
            select(
                MetricSnapshot.publication_id,
                func.max(MetricSnapshot.captured_at).label("latest"),
            )
            .group_by(MetricSnapshot.publication_id)
            .subquery()
        )
        stmt = (
            select(Video, Script, Publication, MetricSnapshot)
            .join(Script, Script.id == Video.script_id)
            .join(Publication, Publication.video_id == Video.id)
            .join(latest_subq, latest_subq.c.publication_id == Publication.id)
            .join(
                MetricSnapshot,
                (MetricSnapshot.publication_id == Publication.id)
                & (MetricSnapshot.captured_at == latest_subq.c.latest),
            )
            .where(Video.niche_id == niche_uuid)
            .order_by(desc(MetricSnapshot.views))
        )
        rows = s.execute(stmt).all()

        if len(rows) < MIN_VIDEOS_FOR_LEARNINGS:
            log.info(
                "weekly_learnings.not_enough_data",
                extra={"niche_id": niche_id, "n_videos": len(rows)},
            )
            return {
                "niche_id": niche_id,
                "skipped": True,
                "reason": (
                    f"need >= {MIN_VIDEOS_FOR_LEARNINGS} videos with snapshots, "
                    f"have {len(rows)}"
                ),
            }

        decile = max(DECILE_FLOOR, len(rows) // 10)
        # Sort by views_per_cent (margin proxy) for the top/bottom split
        scored = [(_video_summary(v, sc, m, p.external_id), m.views) for v, sc, p, m in rows]
        scored.sort(key=lambda x: x[0]["views_per_cent"], reverse=True)
        top = [s[0] for s in scored[:decile]]
        bottom = [s[0] for s in scored[-decile:]]

    system = load_prompt("learnings_v1.md")
    user_msg = json.dumps(
        {
            "niche": niche_slug,
            "top_decile": top,
            "bottom_decile": bottom,
        },
        ensure_ascii=False,
    )
    resp = llm_call(
        model=LEARNINGS_MODEL,
        system=system,
        user=user_msg,
        max_tokens=2048,
        cache_system=True,
    )

    with session_scope() as s:
        record_llm(
            s,
            niche_id=niche_uuid,
            model=resp.usage.model,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            cache_read_tokens=resp.usage.cache_read_tokens,
            cache_write_tokens=resp.usage.cache_write_tokens,
            meta={
                "task": "weekly_learnings",
                "prompt_version": LEARNINGS_PROMPT_VERSION,
                "n_top": len(top),
                "n_bottom": len(bottom),
            },
        )

    key = learnings_key(niche_uuid)
    upload_bytes(key, resp.text.encode("utf-8"), content_type="text/markdown")

    log.info(
        "weekly_learnings.done",
        extra={
            "niche_id": niche_id,
            "key": key,
            "tokens_out": resp.usage.output_tokens,
        },
    )
    return {
        "niche_id": niche_id,
        "niche_slug": niche_slug,
        "n_top": len(top),
        "n_bottom": len(bottom),
        "learnings_key": key,
        "tokens_out": resp.usage.output_tokens,
    }


@shared_task(
    name="shortstack_worker.tasks.analytics.weekly_learnings_all",
    acks_late=True,
)
def weekly_learnings_all() -> dict[str, Any]:
    """Beat-fired Sunday 02:00 UTC. Fans out weekly_learnings per niche."""
    with session_scope() as s:
        niche_ids = [str(n.id) for n in s.execute(select(Niche)).scalars()]
    for nid in niche_ids:
        weekly_learnings.apply_async(args=[nid])
    log.info("analytics.weekly_learnings_all", extra={"queued": len(niche_ids)})
    return {"queued": len(niche_ids), "niche_ids": niche_ids}


def schedule_post_publish_snapshots(publication_id: str) -> list[str]:
    """Called from publish_video. Schedules snapshot ETAs at t+24h / 72h / 7d.

    Returns the celery task ids so the caller can record them if needed.
    """
    now = datetime.now(tz=timezone.utc)
    deltas = (timedelta(hours=24), timedelta(hours=72), timedelta(days=7))
    task_ids: list[str] = []
    for delta in deltas:
        async_result = snapshot_metrics.apply_async(
            args=[publication_id],
            eta=now + delta,
        )
        task_ids.append(async_result.id)
    return task_ids
