from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from ..enums import TrendSource


class TrendItem(BaseModel):
    """Normalized trend record produced by a source fetcher."""

    model_config = ConfigDict(from_attributes=True)

    source: TrendSource
    external_id: str
    title: str
    url: HttpUrl | None = None
    summary: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime


class TrendCluster(BaseModel):
    """Output of Haiku-driven near-duplicate clustering + hook scoring."""

    cluster_id: UUID
    member_external_ids: list[str]
    hook_score: int = Field(ge=1, le=10)
    rationale: str
