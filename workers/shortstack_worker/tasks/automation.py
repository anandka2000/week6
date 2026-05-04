"""Phase 9 automation: produce + publish-approved + nightly fan-out.

  daily_pipeline(niche_id, max_videos=None)
    Run trends → cluster → pick → script → assets → render up to
    ``min(max_videos, niche.daily_quota - already_today)`` times. Each
    sub-task is itself idempotent and individually retryable; this task
    catches per-video exceptions and continues to the next quota slot.

  daily_pipeline_all()
    Beat-fired (10:00 UTC). Fans out daily_pipeline per niche.

  publish_approved(niche_id, platform="youtube_shorts", visibility="unlisted")
    Find videos in this niche with status=APPROVED and no Publication
    for the target platform, queue publish_video for each.

  publish_approved_all()
    Beat-fired (11:00 UTC; 1h after daily_pipeline_all so auto-approved
    videos can still be human-rejected via /review during that gap).
    Fans out per niche.

The daily_pipeline calls each step via ``.run(...)`` (inline) so one
niche's chain is sequential — the cost cap can short-circuit a video
mid-stream without contaminating other niches' runs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import and_, func, select

from shortstack_core.db import Niche, Publication, Video, session_scope
from shortstack_core.enums import Platform, VideoStatus

from ..celery_app import app  # noqa: F401  (ensures app is registered)

log = get_task_logger(__name__)


def _today_video_count(niche_id: UUID) -> int:
    """Count videos created today for this niche (UTC day boundary)."""
    today_start = (
        datetime.now(tz=timezone.utc)
        .replace(hour=0, minute=0, second=0, microsecond=0)
    )
    with session_scope() as s:
        return s.execute(
            select(func.count(Video.id))
            .where(Video.niche_id == niche_id)
            .where(Video.created_at >= today_start)
        ).scalar_one()


@shared_task(
    name="shortstack_worker.tasks.automation.daily_pipeline",
    acks_late=True,
)
def daily_pipeline(niche_id: str, max_videos: int | None = None) -> dict[str, Any]:
    niche_uuid = UUID(niche_id)

    with session_scope() as s:
        niche = s.get(Niche, niche_uuid)
        if niche is None:
            raise ValueError(f"niche {niche_id} not found")
        quota = max_videos if max_videos is not None else niche.daily_quota
        niche_slug = niche.slug

    today_count = _today_video_count(niche_uuid)
    needed = max(0, quota - today_count)
    if needed == 0:
        log.info(
            "daily_pipeline.quota_met",
            extra={
                "niche_id": niche_id,
                "today": today_count,
                "quota": quota,
            },
        )
        return {
            "niche_id": niche_id,
            "niche_slug": niche_slug,
            "skipped": True,
            "reason": "quota_met",
            "today": today_count,
            "quota": quota,
            "produced": [],
        }

    # Imports are local so this module doesn't trip the celery_app's circular
    # include= ordering at startup.
    from .assets import generate_assets
    from .render import render_video
    from .scripts import generate_script
    from .trends import cluster, fetch_reddit, pick_next

    log.info(
        "daily_pipeline.start",
        extra={"niche_id": niche_id, "needed": needed, "quota": quota},
    )

    # 1. Refresh trends (idempotent: source rows have unique constraints).
    # Pre-loop failures degrade gracefully — without this, an Anthropic
    # outage during cluster() (or a missing API key) would crash the whole
    # daily run instead of returning a meaningful "skipped" summary.
    try:
        fetch_reddit.run(niche_id)
        cluster.run(niche_id)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "daily_pipeline.trends_unavailable",
            extra={
                "niche_id": niche_id,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
        return {
            "niche_id": niche_id,
            "niche_slug": niche_slug,
            "skipped": True,
            "reason": f"trends_unavailable: {type(exc).__name__}: {exc}",
            "today": today_count,
            "quota": quota,
            "produced": [],
        }

    produced: list[str] = []
    skipped: list[dict[str, Any]] = []

    for slot in range(needed):
        picked = pick_next.run(niche_id)
        if picked is None:
            log.info(
                "daily_pipeline.no_more_trends",
                extra={"niche_id": niche_id, "slot": slot},
            )
            skipped.append({"slot": slot, "reason": "no_eligible_trends"})
            break

        try:
            script_result = generate_script.run(picked["trend_id"])
            video_id = script_result["video_id"]

            if script_result["status"] == VideoStatus.FAILED.value:
                # Cost-cap-estimate fail-fast already happened in script-gen.
                # Don't run assets / render — the video is already failed.
                skipped.append(
                    {
                        "slot": slot,
                        "trend_id": picked["trend_id"],
                        "video_id": video_id,
                        "reason": "cost_cap_estimate",
                    }
                )
                continue

            generate_assets.run(video_id)
            render_video.run(video_id)
            produced.append(video_id)

        except Exception as exc:  # noqa: BLE001 — keep producing other slots
            log.warning(
                "daily_pipeline.slot_failed",
                extra={
                    "niche_id": niche_id,
                    "slot": slot,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            skipped.append({"slot": slot, "reason": f"{type(exc).__name__}: {exc}"})

    log.info(
        "daily_pipeline.done",
        extra={
            "niche_id": niche_id,
            "produced": len(produced),
            "skipped": len(skipped),
            "today_after": today_count + len(produced),
        },
    )
    return {
        "niche_id": niche_id,
        "niche_slug": niche_slug,
        "produced": produced,
        "skipped": skipped,
        "quota": quota,
        "today_before": today_count,
        "today_after": today_count + len(produced),
    }


@shared_task(
    name="shortstack_worker.tasks.automation.daily_pipeline_all",
    acks_late=True,
)
def daily_pipeline_all() -> dict[str, Any]:
    """Beat-fired (10:00 UTC). Fans out daily_pipeline per niche."""
    with session_scope() as s:
        niche_ids = [str(n.id) for n in s.execute(select(Niche)).scalars()]
    for nid in niche_ids:
        daily_pipeline.apply_async(args=[nid])
    log.info("automation.daily_pipeline_all", extra={"queued": len(niche_ids)})
    return {"queued": len(niche_ids), "niche_ids": niche_ids}


@shared_task(
    name="shortstack_worker.tasks.automation.publish_approved",
    acks_late=True,
)
def publish_approved(
    niche_id: str,
    platform: str = "youtube_shorts",
    visibility: str = "unlisted",
) -> dict[str, Any]:
    """Queue publish_video for every APPROVED video in the niche that has no
    Publication for the target platform yet."""
    niche_uuid = UUID(niche_id)
    plat = Platform(platform)

    with session_scope() as s:
        # videos with status=APPROVED and no Publication for this platform
        existing_pub = (
            select(Publication.video_id)
            .where(Publication.platform == plat)
            .scalar_subquery()
        )
        rows = (
            s.execute(
                select(Video.id)
                .where(
                    and_(
                        Video.niche_id == niche_uuid,
                        Video.status == VideoStatus.APPROVED,
                        Video.id.not_in(existing_pub),
                    )
                )
                .order_by(Video.created_at)
            )
            .scalars()
            .all()
        )
        ids = [str(vid) for vid in rows]

    from .publish import publish_video

    for vid in ids:
        publish_video.apply_async(args=[vid, platform, visibility])

    log.info(
        "automation.publish_approved",
        extra={
            "niche_id": niche_id,
            "platform": platform,
            "queued": len(ids),
        },
    )
    return {
        "niche_id": niche_id,
        "platform": platform,
        "queued": ids,
    }


@shared_task(
    name="shortstack_worker.tasks.automation.publish_approved_all",
    acks_late=True,
)
def publish_approved_all() -> dict[str, Any]:
    """Beat-fired (11:00 UTC). Fans out publish_approved per niche, default
    YouTube Shorts unlisted."""
    with session_scope() as s:
        niche_ids = [str(n.id) for n in s.execute(select(Niche)).scalars()]
    for nid in niche_ids:
        publish_approved.apply_async(args=[nid])
    log.info("automation.publish_approved_all", extra={"queued": len(niche_ids)})
    return {"queued": len(niche_ids), "niche_ids": niche_ids}
