from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MetricSnapshot(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    publication_id: UUID
    captured_at: datetime
    views: int = 0
    avg_view_duration_sec: float = 0.0
    retention_curve: list[float] = Field(default_factory=list)
    ctr: float | None = None
    likes: int = 0
    comments: int = 0
    shares: int = 0
