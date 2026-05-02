"""Centralized settings for ShortStack. Loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
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

    # Image gen
    replicate_api_token: str = ""
    pexels_api_key: str = ""
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

    # Render service
    render_service_url: str = "http://localhost:8787"

    # Cost caps (cents)
    cost_soft_cap_cents: int = Field(default=75, ge=1)
    cost_hard_cap_cents: int = Field(default=100, ge=1)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
