"""Niche persona shape (stored as JSONB on niches.persona_json)."""

from __future__ import annotations

from pydantic import BaseModel, Field

# Sentinel value for ``NichePersona.voice_id`` used by the seeder until an
# operator pins a real ElevenLabs voice. Producers (TTS) and the e2e stub
# both check against this constant so the literal lives in one place.
VOICE_ID_PLACEHOLDER = "REPLACE_WITH_ELEVENLABS_VOICE_ID"


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
