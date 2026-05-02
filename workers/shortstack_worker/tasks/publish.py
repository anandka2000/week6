"""Phase 5 publish: upload approved videos to platforms.

  publish_video(video_id, platform="youtube_shorts", visibility="unlisted")
    1. Idempotency check: if a Publication for (video_id, platform) already
       exists, return its info and skip.
    2. Status guard: video must be APPROVED. Transition APPROVED -> PUBLISHING
       so a duplicate task call sees the in-flight state.
    3. Download mp4 from S3, build VideoMetadata from script + persona, call
       the platform's Publisher.
    4. On success: insert Publication row, transition -> PUBLISHED.
    5. On PublishError: roll status back to APPROVED so an operator (or a
       follow-up cron) can retry. ``failure_reason`` carries the error.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select

from shortstack_core.db import Niche, Publication, Script, Video, session_scope
from shortstack_core.enums import Platform, VideoStatus, Visibility
from shortstack_core.schemas import NichePersona, ScriptDraft
from shortstack_core.storage import download_bytes
from shortstack_publishers import (
    Publisher,
    PublishError,
    VideoMetadata,
    YouTubeShortsPublisher,
)

from ..celery_app import app  # noqa: F401  (ensures app is registered)

log = get_task_logger(__name__)

# YouTube tag-list total length cap (sum of len(tag) + 1 for commas).
YOUTUBE_TAG_TOTAL_CAP = 500


def _publisher_for(platform: Platform) -> Publisher:
    if platform is Platform.YOUTUBE_SHORTS:
        return YouTubeShortsPublisher()
    raise ValueError(f"no publisher implementation for platform {platform.value}")


def _build_video_metadata(
    draft: ScriptDraft,
    persona: NichePersona,
    *,
    visibility: Visibility = Visibility.UNLISTED,
) -> VideoMetadata:
    """Pure helper: assemble the YouTube-bound metadata from script + persona."""
    description = "\n\n".join(
        [
            draft.hook,
            draft.cta,
            "— Made with the help of AI tools. #AI #Shorts",
        ]
    )[:5000]

    raw_tags = list(
        dict.fromkeys(
            [
                "AI",
                "Shorts",
                persona.brand,
            ]
        )
    )
    # YouTube enforces a ~500-char total across the tags array.
    tags: list[str] = []
    used = 0
    for t in raw_tags:
        if used + len(t) + 1 > YOUTUBE_TAG_TOTAL_CAP:
            break
        tags.append(t)
        used += len(t) + 1

    return VideoMetadata(
        title=draft.hook[:100],
        description=description,
        tags=tags,
        visibility=visibility,
        contains_synthetic_media=True,
        made_for_kids=False,
    )


@shared_task(
    name="shortstack_worker.tasks.publish.publish_video",
    autoretry_for=(),  # publish-time retries are an operator decision in v0
    acks_late=True,
)
def publish_video(
    video_id: str,
    platform: str = "youtube_shorts",
    visibility: str = "unlisted",
) -> dict[str, Any]:
    video_uuid = UUID(video_id)
    plat = Platform(platform)
    vis = Visibility(visibility)

    # Idempotency + status guard in one tx
    with session_scope() as s:
        existing = s.execute(
            select(Publication)
            .where(Publication.video_id == video_uuid)
            .where(Publication.platform == plat)
        ).scalar_one_or_none()
        if existing is not None:
            log.info(
                "publish.skip_idempotent",
                extra={
                    "video_id": video_id,
                    "platform": plat.value,
                    "external_id": existing.external_id,
                },
            )
            return {
                "video_id": video_id,
                "platform": plat.value,
                "external_id": existing.external_id,
                "external_url": existing.external_url,
                "skipped": True,
            }

        video = s.get(Video, video_uuid)
        if video is None:
            raise ValueError(f"video {video_id} not found")
        if video.status != VideoStatus.APPROVED:
            raise ValueError(
                f"video {video_id} status is {video.status.value} (expected approved)"
            )
        if not video.s3_key_mp4:
            raise ValueError(
                f"video {video_id} is approved but has no rendered mp4"
            )

        script = s.get(Script, video.script_id)
        niche = s.get(Niche, video.niche_id)
        if script is None or niche is None:
            raise ValueError(f"missing script or niche for video {video_id}")
        draft = ScriptDraft.model_validate(script.draft_json)
        persona = NichePersona.model_validate(niche.persona_json)
        s3_key = video.s3_key_mp4

        # Move to PUBLISHING so a duplicate dispatch sees it and skips
        video.status = VideoStatus.PUBLISHING
        video.failure_reason = None

    log.info("publish.download_mp4", extra={"video_id": video_id, "s3_key": s3_key})
    video_bytes = download_bytes(s3_key)
    metadata = _build_video_metadata(draft, persona, visibility=vis)

    publisher = _publisher_for(plat)
    log.info(
        "publish.uploading",
        extra={
            "video_id": video_id,
            "platform": plat.value,
            "size_bytes": len(video_bytes),
            "title": metadata.title,
        },
    )
    try:
        result = publisher.publish(video_bytes, metadata)
    except PublishError as exc:
        # Roll status back so a retry is possible. Keep failure_reason for forensics.
        with session_scope() as s:
            v = s.get(Video, video_uuid)
            if v is not None:
                v.status = VideoStatus.APPROVED
                v.failure_reason = f"publish_failed: {exc}"
        raise

    # Persist publication + flip to PUBLISHED in one tx
    with session_scope() as s:
        publication = Publication(
            video_id=video_uuid,
            platform=plat,
            external_id=result.external_id,
            external_url=str(result.external_url),
            visibility=vis,
            meta=result.raw,
        )
        s.add(publication)
        s.flush()
        publication_id = str(publication.id)

        v = s.get(Video, video_uuid)
        if v is not None:
            v.status = VideoStatus.PUBLISHED
            v.failure_reason = None

    # Schedule t+24h / 72h / 7d metric snapshots. Best-effort — beat-driven
    # nightly_catchup re-snapshots anything missed if the eta'd tasks are lost.
    snapshot_task_ids: list[str] = []
    try:
        from .analytics import schedule_post_publish_snapshots

        snapshot_task_ids = schedule_post_publish_snapshots(publication_id)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "publish.schedule_snapshots_failed",
            extra={"publication_id": publication_id, "error": str(exc)},
        )

    log.info(
        "publish.done",
        extra={
            "video_id": video_id,
            "publication_id": publication_id,
            "external_id": result.external_id,
            "snapshot_etas": len(snapshot_task_ids),
        },
    )
    return {
        "video_id": video_id,
        "publication_id": publication_id,
        "platform": plat.value,
        "external_id": result.external_id,
        "external_url": str(result.external_url),
        "visibility": vis.value,
        "snapshot_task_ids": snapshot_task_ids,
        "next_status": VideoStatus.PUBLISHED.value,
    }
