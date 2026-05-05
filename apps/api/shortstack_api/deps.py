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


def get_niche_by_slug(niche: str, db: Session = Depends(get_db)) -> Niche:
    """Resolve a niche by its slug. The query parameter is named ``niche``
    (not ``slug``) because that's what the dashboard's fetch helpers send;
    keeping them aligned avoids 422 'field required' errors at the dashboard
    boundary. The function name still reads ``by_slug`` because it looks up
    the row via ``Niche.slug``.
    """
    n = db.query(Niche).filter(Niche.slug == niche).one_or_none()
    if n is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"niche '{niche}' not found",
        )
    return n
