"""GET /metrics — per-video latest-snapshot rollup with margin proxy."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from shortstack_core.db import MetricSnapshot, Niche, Publication, Video
from shortstack_core.enums import VideoStatus

from ..deps import get_db, get_niche_by_slug

router = APIRouter(prefix="/metrics", tags=["metrics"])


class VideoMetricRollup(BaseModel):
    """Latest metrics for a published video, with cost + margin proxy."""

    model_config = ConfigDict(from_attributes=True)

    video_id: UUID
    status: VideoStatus
    external_url: str | None = None
    cost_cents: int
    cost_estimate_cents: int
    views: int = 0
    likes: int = 0
    comments: int = 0
    captured_at: datetime | None = None
    # views per cent of actual cost — the margin proxy
    views_per_cent: float = 0.0


@router.get("/by-video", response_model=list[VideoMetricRollup])
def metrics_by_video(
    niche: Niche = Depends(get_niche_by_slug),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[VideoMetricRollup]:
    """Latest snapshot per video, joined to cost. Sorted by views desc."""
    latest_subq = (
        select(
            MetricSnapshot.publication_id,
            func.max(MetricSnapshot.captured_at).label("latest"),
        )
        .group_by(MetricSnapshot.publication_id)
        .subquery()
    )

    stmt = (
        select(Video, Publication, MetricSnapshot)
        .join(Publication, Publication.video_id == Video.id, isouter=True)
        .join(
            latest_subq,
            latest_subq.c.publication_id == Publication.id,
            isouter=True,
        )
        .join(
            MetricSnapshot,
            (MetricSnapshot.publication_id == Publication.id)
            & (MetricSnapshot.captured_at == latest_subq.c.latest),
            isouter=True,
        )
        .where(Video.niche_id == niche.id)
        .order_by(desc(MetricSnapshot.views), desc(Video.created_at))
        .limit(limit)
    )

    out: list[VideoMetricRollup] = []
    for video, publication, snap in db.execute(stmt).all():
        cost = max(int(video.cost_cents), 1)
        views = int(snap.views) if snap is not None else 0
        out.append(
            VideoMetricRollup(
                video_id=video.id,
                status=video.status,
                external_url=publication.external_url if publication is not None else None,
                cost_cents=int(video.cost_cents),
                cost_estimate_cents=int(video.cost_estimate_cents),
                views=views,
                likes=int(snap.likes) if snap is not None else 0,
                comments=int(snap.comments) if snap is not None else 0,
                captured_at=snap.captured_at if snap is not None else None,
                views_per_cent=round(views / cost, 2),
            )
        )
    return out
