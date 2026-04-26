"""SQLAlchemy 2.0 models. Single file for v0; split if it grows past ~500 lines."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .. import enums


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB}


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _enum_col(py_enum: type, **kw: Any) -> sa.Column:
    return mapped_column(
        sa.Enum(py_enum, native_enum=False, length=32, validate_strings=True),
        **kw,
    )


def _ts() -> Mapped[datetime]:
    return mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class Niche(Base):
    __tablename__ = "niches"

    id: Mapped[uuid.UUID] = _pk()
    slug: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    persona_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    cost_cap_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=100)
    daily_quota: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=3)
    created_at: Mapped[datetime] = _ts()


class Trend(Base):
    __tablename__ = "trends"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_trends_source_external_id"),
        Index("ix_trends_niche_fetched_at", "niche_id", sa.text("fetched_at DESC")),
        Index("ix_trends_cluster_id", "cluster_id"),
    )

    id: Mapped[uuid.UUID] = _pk()
    niche_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("niches.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[enums.TrendSource] = _enum_col(enums.TrendSource, nullable=False)
    external_id: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    url: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    hook_score: Mapped[int | None] = mapped_column(sa.SmallInteger, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[uuid.UUID] = _pk()
    trend_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trends.id", ondelete="SET NULL"), nullable=True
    )
    niche_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("niches.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[enums.ScriptMode] = _enum_col(
        enums.ScriptMode, nullable=False, default=enums.ScriptMode.TREND
    )
    input_text: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    draft_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    prompt_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[enums.ScriptStatus] = _enum_col(
        enums.ScriptStatus, nullable=False, default=enums.ScriptStatus.DRAFT
    )
    created_at: Mapped[datetime] = _ts()


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        Index("ix_assets_script_id", "script_id"),
    )

    id: Mapped[uuid.UUID] = _pk()
    script_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[enums.AssetKind] = _enum_col(enums.AssetKind, nullable=False)
    scene_index: Mapped[int | None] = mapped_column(sa.SmallInteger, nullable=True)
    provider: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    s3_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = _ts()


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = _pk()
    script_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scripts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    niche_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("niches.id", ondelete="CASCADE"), nullable=False
    )
    s3_key_mp4: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    duration_sec: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), nullable=True)
    status: Mapped[enums.VideoStatus] = _enum_col(
        enums.VideoStatus, nullable=False, default=enums.VideoStatus.PENDING_ASSETS
    )
    cost_estimate_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    cost_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    failure_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )


class Publication(Base):
    __tablename__ = "publications"
    __table_args__ = (
        UniqueConstraint("video_id", "platform", name="uq_publications_video_platform"),
    )

    id: Mapped[uuid.UUID] = _pk()
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[enums.Platform] = _enum_col(enums.Platform, nullable=False)
    external_id: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    external_url: Mapped[str] = mapped_column(sa.Text, nullable=False)
    visibility: Mapped[enums.Visibility] = _enum_col(
        enums.Visibility, nullable=False, default=enums.Visibility.UNLISTED
    )
    published_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = (
        Index(
            "ix_metric_snapshots_publication_captured",
            "publication_id",
            sa.text("captured_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publications.id", ondelete="CASCADE"), nullable=False
    )
    captured_at: Mapped[datetime] = _ts()
    views: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    avg_view_duration_sec: Mapped[Decimal] = mapped_column(
        sa.Numeric(8, 2), nullable=False, default=0
    )
    retention_curve: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    ctr: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 4), nullable=True)
    likes: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    comments: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    shares: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)


class CostEvent(Base):
    __tablename__ = "cost_events"
    __table_args__ = (
        Index("ix_cost_events_video_id", "video_id"),
        Index("ix_cost_events_niche_created", "niche_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    video_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="SET NULL"), nullable=True
    )
    niche_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("niches.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[enums.CostKind] = _enum_col(enums.CostKind, nullable=False)
    provider: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    model: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    units: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False, default=0)
    cost_cents: Mapped[Decimal] = mapped_column(sa.Numeric(8, 3), nullable=False, default=0)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = _ts()
