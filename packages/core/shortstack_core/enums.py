"""String enums shared by Pydantic schemas and SQLAlchemy models."""

from __future__ import annotations

from enum import Enum


class TrendSource(str, Enum):
    REDDIT = "reddit"
    YOUTUBE = "youtube"
    GTRENDS = "gtrends"


class ScriptMode(str, Enum):
    TREND = "trend"
    STORY = "story"


class ScriptStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    REJECTED = "rejected"


class AssetKind(str, Enum):
    IMAGE = "image"
    AUDIO_VOICE = "audio_voice"
    AUDIO_MUSIC = "audio_music"
    CAPTIONS_JSON = "captions_json"


class VideoStatus(str, Enum):
    PENDING_ASSETS = "pending_assets"
    PENDING_RENDER = "pending_render"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class Platform(str, Enum):
    YOUTUBE_SHORTS = "youtube_shorts"
    IG_REELS = "ig_reels"
    TIKTOK = "tiktok"
    X = "x"
    LINKEDIN = "linkedin"


class Visibility(str, Enum):
    UNLISTED = "unlisted"
    PUBLIC = "public"


class CostKind(str, Enum):
    LLM = "llm"
    TTS = "tts"
    IMAGE = "image"
    RENDER = "render"
    STORAGE = "storage"
    API = "api"
