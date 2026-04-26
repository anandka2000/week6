"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from shortstack_core.db import Niche, get_sessionmaker


def get_db() -> Iterator[Session]:
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_niche_by_slug(slug: str, db: Session = Depends(get_db)) -> Niche:
    niche = db.query(Niche).filter(Niche.slug == slug).one_or_none()
    if niche is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"niche '{slug}' not found"
        )
    return niche
