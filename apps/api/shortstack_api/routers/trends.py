from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from shortstack_core.db import Niche, Trend

from ..deps import get_db, get_niche_by_slug
from ..serializers import TrendRead

router = APIRouter(prefix="/trends", tags=["trends"])

RECENCY_HOURS = 48


@router.get("", response_model=list[TrendRead])
def list_trends(
    niche: Niche = Depends(get_niche_by_slug),
    limit: int = Query(50, ge=1, le=200),
    only_unconsumed: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> list[TrendRead]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=RECENCY_HOURS)
    stmt = (
        select(Trend)
        .where(Trend.niche_id == niche.id)
        .where(Trend.fetched_at >= cutoff)
        .order_by(Trend.hook_score.desc().nulls_last(), Trend.fetched_at.desc())
        .limit(limit)
    )
    if only_unconsumed:
        stmt = stmt.where(Trend.consumed_at.is_(None))
    rows = db.execute(stmt).scalars().all()
    return [TrendRead.model_validate(r) for r in rows]
