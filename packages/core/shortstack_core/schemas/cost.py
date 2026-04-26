from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..enums import CostKind


class CostEvent(BaseModel):
    """One row per paid action. Roll up to videos.cost_cents."""

    model_config = ConfigDict(from_attributes=True)

    video_id: UUID | None = None
    niche_id: UUID
    kind: CostKind
    provider: str
    model: str | None = None
    units: float = Field(ge=0, description="tokens, characters, images, or seconds")
    cost_cents: float = Field(ge=0)
    meta: dict[str, Any] = Field(default_factory=dict)
