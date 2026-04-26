from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from shortstack_core.db import Niche
from shortstack_core.schemas import NichePersona

from ..deps import get_db
from ..serializers import NicheRead

router = APIRouter(prefix="/niches", tags=["niches"])


def _to_read(n: Niche) -> NicheRead:
    return NicheRead(
        id=n.id,
        slug=n.slug,
        name=n.name,
        cost_cap_cents=n.cost_cap_cents,
        daily_quota=n.daily_quota,
        persona=NichePersona.model_validate(n.persona_json),
        created_at=n.created_at,
    )


@router.get("", response_model=list[NicheRead])
def list_niches(db: Session = Depends(get_db)) -> list[NicheRead]:
    rows = db.execute(select(Niche).order_by(Niche.created_at)).scalars().all()
    return [_to_read(n) for n in rows]
