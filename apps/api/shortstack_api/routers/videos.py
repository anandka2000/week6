from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from shortstack_core.db import Niche, Publication, Video
from shortstack_core.enums import VideoStatus

from ..deps import get_db, get_niche_by_slug
from ..serializers import PublicationRead, VideoRead

router = APIRouter(tags=["videos"])


@router.get("/videos", response_model=list[VideoRead])
def list_videos(
    niche: Niche = Depends(get_niche_by_slug),
    limit: int = Query(50, ge=1, le=200),
    statuses: list[VideoStatus] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[VideoRead]:
    stmt = (
        select(Video)
        .where(Video.niche_id == niche.id)
        .order_by(Video.created_at.desc())
        .limit(limit)
    )
    if statuses:
        stmt = stmt.where(Video.status.in_(statuses))
    return [VideoRead.model_validate(v) for v in db.execute(stmt).scalars()]


@router.get("/publications", response_model=list[PublicationRead])
def list_publications(
    niche: Niche = Depends(get_niche_by_slug),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[PublicationRead]:
    stmt = (
        select(Publication)
        .join(Video, Video.id == Publication.video_id)
        .where(Video.niche_id == niche.id)
        .order_by(Publication.published_at.desc())
        .limit(limit)
    )
    return [PublicationRead.model_validate(p) for p in db.execute(stmt).scalars()]


def _transition(
    db: Session,
    video_id: UUID,
    *,
    frm: set[VideoStatus],
    to: VideoStatus,
    failure_reason: str | None = None,
) -> Video:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"video {video_id} not found")
    if video.status not in frm:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"cannot transition from {video.status} to {to}",
        )
    video.status = to
    if failure_reason is not None:
        video.failure_reason = failure_reason
    db.commit()
    db.refresh(video)
    return video


@router.post("/videos/{video_id}/approve", response_model=VideoRead)
def approve(video_id: UUID, db: Session = Depends(get_db)) -> VideoRead:
    v = _transition(
        db, video_id, frm={VideoStatus.PENDING_REVIEW}, to=VideoStatus.APPROVED
    )
    return VideoRead.model_validate(v)


@router.post("/videos/{video_id}/reject", response_model=VideoRead)
def reject(video_id: UUID, db: Session = Depends(get_db)) -> VideoRead:
    v = _transition(
        db,
        video_id,
        frm={VideoStatus.PENDING_REVIEW},
        to=VideoStatus.FAILED,
        failure_reason="rejected_in_review",
    )
    return VideoRead.model_validate(v)
