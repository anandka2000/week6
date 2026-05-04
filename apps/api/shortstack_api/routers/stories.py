"""Phase 8: user-story mode entry point.

POST /videos/from-story  -> runs ``generate_script_from_story`` synchronously
and returns the resulting script + video ids. Sync (``task.run``) for v0
simplicity: the operator is blocked anyway, and we want to surface the
``video_id`` immediately so the dashboard can link to /videos.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from shortstack_core.db import Niche
from shortstack_core.enums import VideoStatus
from shortstack_worker.tasks.scripts import generate_script_from_story

from ..deps import get_db
from ..serializers import StoryAccepted, StoryIn

router = APIRouter(tags=["stories"])


@router.post(
    "/videos/from-story",
    response_model=StoryAccepted,
    status_code=status.HTTP_201_CREATED,
)
def from_story(
    payload: StoryIn,
    db: Session = Depends(get_db),
) -> StoryAccepted:
    niche = db.query(Niche).filter(Niche.slug == payload.niche_slug).one_or_none()
    if niche is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"niche '{payload.niche_slug}' not found",
        )

    try:
        result = generate_script_from_story.run(str(niche.id), payload.story_text)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return StoryAccepted(
        script_id=UUID(result["script_id"]),
        video_id=UUID(result["video_id"]),
        estimate_cents=result["estimate_cents"],
        status=VideoStatus(result["status"]),
    )
