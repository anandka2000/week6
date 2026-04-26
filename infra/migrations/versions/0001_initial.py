"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Allowed enum values are enforced as CHECK constraints (native_enum=False).
TREND_SOURCE = ("reddit", "youtube", "gtrends")
SCRIPT_MODE = ("trend", "story")
SCRIPT_STATUS = ("draft", "validated", "rejected")
ASSET_KIND = ("image", "audio_voice", "audio_music", "captions_json")
VIDEO_STATUS = (
    "pending_assets",
    "pending_render",
    "pending_review",
    "approved",
    "publishing",
    "published",
    "failed",
)
PLATFORM = ("youtube_shorts", "ig_reels", "tiktok", "x", "linkedin")
VISIBILITY = ("unlisted", "public")
COST_KIND = ("llm", "tts", "image", "render", "storage", "api")


def _enum(name: str, values: tuple[str, ...]) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, length=32)


def upgrade() -> None:
    op.create_table(
        "niches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("persona_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("cost_cap_cents", sa.Integer, nullable=False, server_default="100"),
        sa.Column("daily_quota", sa.Integer, nullable=False, server_default="3"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "trends",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "niche_id",
            UUID(as_uuid=True),
            sa.ForeignKey("niches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", _enum("trend_source", TREND_SOURCE), nullable=False),
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("url", sa.Text),
        sa.Column("summary", sa.Text),
        sa.Column("raw_payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("cluster_id", UUID(as_uuid=True)),
        sa.Column("hook_score", sa.SmallInteger),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("source", "external_id", name="uq_trends_source_external_id"),
    )
    op.create_index(
        "ix_trends_niche_fetched_at",
        "trends",
        ["niche_id", sa.text("fetched_at DESC")],
    )
    op.create_index("ix_trends_cluster_id", "trends", ["cluster_id"])

    op.create_table(
        "scripts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "trend_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trends.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "niche_id",
            UUID(as_uuid=True),
            sa.ForeignKey("niches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mode",
            _enum("script_mode", SCRIPT_MODE),
            nullable=False,
            server_default="trend",
        ),
        sa.Column("input_text", sa.Text),
        sa.Column("draft_json", JSONB, nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column(
            "status",
            _enum("script_status", SCRIPT_STATUS),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "script_id",
            UUID(as_uuid=True),
            sa.ForeignKey("scripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", _enum("asset_kind", ASSET_KIND), nullable=False),
        sa.Column("scene_index", sa.SmallInteger),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("s3_key", sa.Text, nullable=False),
        sa.Column("meta", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_assets_script_id", "assets", ["script_id"])

    op.create_table(
        "videos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "script_id",
            UUID(as_uuid=True),
            sa.ForeignKey("scripts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "niche_id",
            UUID(as_uuid=True),
            sa.ForeignKey("niches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("s3_key_mp4", sa.Text),
        sa.Column("duration_sec", sa.Numeric(6, 2)),
        sa.Column(
            "status",
            _enum("video_status", VIDEO_STATUS),
            nullable=False,
            server_default="pending_assets",
        ),
        sa.Column("cost_estimate_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failure_reason", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "publications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "video_id",
            UUID(as_uuid=True),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", _enum("platform", PLATFORM), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("external_url", sa.Text, nullable=False),
        sa.Column(
            "visibility",
            _enum("visibility", VISIBILITY),
            nullable=False,
            server_default="unlisted",
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("meta", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("video_id", "platform", name="uq_publications_video_platform"),
    )

    op.create_table(
        "metric_snapshots",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "publication_id",
            UUID(as_uuid=True),
            sa.ForeignKey("publications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("views", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "avg_view_duration_sec", sa.Numeric(8, 2), nullable=False, server_default="0"
        ),
        sa.Column(
            "retention_curve", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("ctr", sa.Numeric(6, 4)),
        sa.Column("likes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("comments", sa.Integer, nullable=False, server_default="0"),
        sa.Column("shares", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_metric_snapshots_publication_captured",
        "metric_snapshots",
        ["publication_id", sa.text("captured_at DESC")],
    )

    op.create_table(
        "cost_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "video_id",
            UUID(as_uuid=True),
            sa.ForeignKey("videos.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "niche_id",
            UUID(as_uuid=True),
            sa.ForeignKey("niches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", _enum("cost_kind", COST_KIND), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64)),
        sa.Column("units", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cost_cents", sa.Numeric(8, 3), nullable=False, server_default="0"),
        sa.Column("meta", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_cost_events_video_id", "cost_events", ["video_id"])
    op.create_index(
        "ix_cost_events_niche_created", "cost_events", ["niche_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_cost_events_niche_created", table_name="cost_events")
    op.drop_index("ix_cost_events_video_id", table_name="cost_events")
    op.drop_table("cost_events")
    op.drop_index(
        "ix_metric_snapshots_publication_captured", table_name="metric_snapshots"
    )
    op.drop_table("metric_snapshots")
    op.drop_table("publications")
    op.drop_table("videos")
    op.drop_index("ix_assets_script_id", table_name="assets")
    op.drop_table("assets")
    op.drop_table("scripts")
    op.drop_index("ix_trends_cluster_id", table_name="trends")
    op.drop_index("ix_trends_niche_fetched_at", table_name="trends")
    op.drop_table("trends")
    op.drop_table("niches")
