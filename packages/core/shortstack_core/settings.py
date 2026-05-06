"""Centralized settings for ShortStack. Loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Postgres
    database_url: str = "postgresql+psycopg://shortstack:shortstack@localhost:5432/shortstack"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO / S3
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "shortstack"
    s3_secret_key: str = "shortstack-dev-secret"
    s3_bucket: str = "shortstack"
    s3_region: str = "us-east-1"

    # LLM
    anthropic_api_key: str = ""
    script_model: str = "claude-sonnet-4-6"
    utility_model: str = "claude-haiku-4-5"

    # TTS
    elevenlabs_api_key: str = ""
    elevenlabs_model: str = "eleven_turbo_v2_5"
    openai_api_key: str = ""

    # Image gen.
    # Vendor naming is inconsistent (Replicate uses _TOKEN, Pexels uses _KEY,
    # everyone else uses _API_KEY). Accept the canonical form plus the
    # likely-typo aliases so a misnamed env var doesn't silently produce
    # an empty key + a confusing "skipping assets" message.
    replicate_api_token: str = Field(
        default="",
        validation_alias=AliasChoices(
            "REPLICATE_API_TOKEN",
            "REPLICATE_API_KEY",
            "REPLICATE_TOKEN",
        ),
    )
    pexels_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "PEXELS_API_KEY",
            "PEXELS_API_TOKEN",
            "PEXELS_KEY",
        ),
    )
    flux_model: str = "black-forest-labs/flux-schnell"

    # Trends
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "shortstack/0.1"
    youtube_api_key: str = ""

    # Publish
    youtube_oauth_client_id: str = ""
    youtube_oauth_client_secret: str = ""
    youtube_oauth_refresh_token: str = ""

    # Multi-platform (Buffer)
    buffer_access_token: str = ""

    # Render service
    render_service_url: str = "http://localhost:8787"

    # Cost caps (cents)
    cost_soft_cap_cents: int = Field(default=75, ge=1)
    cost_hard_cap_cents: int = Field(default=100, ge=1)

    # Phase 9 auto-approve heuristic. Failing any gate holds the video at
    # pending_review; passing all gates flips render_video output straight to
    # APPROVED so the daily cron can publish without human review.
    auto_approve_min_duration_sec: float = Field(default=15.0, ge=1.0)
    auto_approve_max_duration_sec: float = Field(default=60.0, ge=15.0)
    auto_approve_min_words_per_sec: float = Field(default=1.0, ge=0.0)
    auto_approve_max_cost_cents: int = Field(default=200, ge=1)
    auto_approve_flop_threshold_views: int = Field(default=100, ge=0)
    auto_approve_flop_streak: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def _auto_approve_duration_window_consistent(self) -> Settings:
        """Reject min > max so every video doesn't silently trip the duration
        gate. Without this check a typo (env vars swapped) would hold
        every render at pending_review with no obvious cause."""
        if self.auto_approve_min_duration_sec > self.auto_approve_max_duration_sec:
            raise ValueError(
                f"AUTO_APPROVE_MIN_DURATION_SEC ({self.auto_approve_min_duration_sec}) "
                f"> AUTO_APPROVE_MAX_DURATION_SEC ({self.auto_approve_max_duration_sec})"
            )
        return self


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
