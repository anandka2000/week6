from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shortstack_core.db import CostEvent, Niche

from ..deps import get_db, get_niche_by_slug
from ..serializers import DailyCost

router = APIRouter(prefix="/costs", tags=["costs"])


@router.get("/daily", response_model=list[DailyCost])
def daily_costs(
    niche: Niche = Depends(get_niche_by_slug),
    days: int = Query(30, ge=1, le=180),
    db: Session = Depends(get_db),
) -> list[DailyCost]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    day_col = func.date(CostEvent.created_at).label("day")
    total_col = func.sum(CostEvent.cost_cents).label("total_cents")
    stmt = (
        select(day_col, total_col)
        .where(CostEvent.niche_id == niche.id)
        .where(CostEvent.created_at >= cutoff)
        .group_by(day_col)
        .order_by(day_col.desc())
    )
    return [
        DailyCost(day=row.day, total_cents=float(row.total_cents))
        for row in db.execute(stmt).all()
    ]
