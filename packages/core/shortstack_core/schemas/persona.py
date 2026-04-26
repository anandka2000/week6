"""Niche persona shape (stored as JSONB on niches.persona_json)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NichePersona(BaseModel):
    brand: str = Field(description="Channel brand, e.g. 'Trending Tech: AI Productivity'")
    voice_id: str = Field(description="ElevenLabs voice id pinned to this niche")
    tone: str = Field(default="energetic, no-fluff, contrarian-friendly")
    hook_styles: list[str] = Field(
        default_factory=lambda: ["pattern_interrupt", "curiosity_gap", "contrarian"]
    )
    banned_topics: list[str] = Field(default_factory=list)
    cta_template: str = Field(default="Follow for more.")
    subreddits: list[str] = Field(
        default_factory=list,
        description="Subreddits used by the Reddit trends fetcher",
    )
