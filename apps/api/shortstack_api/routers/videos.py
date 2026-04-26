from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from shortstack_core.db import Niche, Publication, Video

from ..deps import get_db, get_niche_by_slug
from ..serializers import PublicationRead, VideoRead

router = APIRouter(tags=["videos"])


@router.get("/videos", response_model=list[VideoRead])
def list_videos(
    niche: Niche = Depends(get_niche_by_slug),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[VideoRead]:
    stmt = (
        select(Video)
        .where(Video.niche_id == niche.id)
        .order_by(Video.created_at.desc())
        .limit(limit)
    )
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
