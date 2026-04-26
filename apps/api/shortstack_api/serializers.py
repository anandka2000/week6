"""API response models. Kept separate from Pydantic schemas in core because
API shapes can drift from internal artifacts (e.g. we expose ``persona`` here
but internally store it as raw JSONB).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shortstack_core.enums import (
    Platform,
    TrendSource,
    VideoStatus,
    Visibility,
)
from shortstack_core.schemas import NichePersona


class NicheRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    cost_cap_cents: int
    daily_quota: int
    persona: NichePersona
    created_at: datetime


class TrendRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: TrendSource
    title: str
    url: str | None
    hook_score: int | None
    cluster_id: UUID | None
    fetched_at: datetime
    consumed_at: datetime | None


class VideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    niche_id: UUID
    status: VideoStatus
    cost_estimate_cents: int
    cost_cents: int
    duration_sec: Decimal | None = None
    s3_key_mp4: str | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class PublicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    video_id: UUID
    platform: Platform
    external_id: str
    external_url: str
    visibility: Visibility
    published_at: datetime


class DailyCost(BaseModel):
    day: date
    total_cents: float = Field(description="sum of cost_events.cost_cents for that day")
