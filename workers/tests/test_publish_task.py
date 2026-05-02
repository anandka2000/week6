"""publish_video task — pure-helper tests. DB / S3 / network paths deferred."""

from __future__ import annotations

import pytest

from shortstack_core.enums import Visibility
from shortstack_core.schemas import NichePersona, Scene, ScriptDraft
from shortstack_worker.tasks.publish import (
    YOUTUBE_TAG_TOTAL_CAP,
    _build_video_metadata,
    _publisher_for,
)


def _persona(brand: str = "Trending Tech: AI Productivity") -> NichePersona:
    return NichePersona(
        brand=brand,
        voice_id="vox-1",
        subreddits=["productivity"],
    )


def _draft(
    hook: str = "Stop scrolling. This one tool runs my whole week.",
    cta: str = "Follow if you want this in your inbox weekly.",
) -> ScriptDraft:
    return ScriptDraft(
        hook=hook,
        scenes=[
            Scene(
                index=0,
                narration="Stop scrolling.",
                on_screen_text="STOP",
                visual_prompt="x",
                duration_sec=2.5,
            ),
            Scene(
                index=1,
                narration="One tool. Whole week.",
                on_screen_text="",
                visual_prompt="x",
                duration_sec=4.0,
            ),
            Scene(
                index=2,
                narration="No exceptions.",
                on_screen_text="",
                visual_prompt="x",
                duration_sec=4.0,
            ),
            Scene(
                index=3,
                narration="Steal it.",
                on_screen_text="",
                visual_prompt="x",
                duration_sec=4.0,
            ),
        ],
        cta=cta,
        total_duration_sec=14.5,
        prompt_version="scripts_v1",
        model="claude-sonnet-4-6",
    )


def test_metadata_title_uses_hook_truncated_to_100():
    long_hook = " ".join(["word"] * 12)  # well under 100 chars but enough words
    meta = _build_video_metadata(_draft(hook=long_hook), _persona())
    assert len(meta.title) <= 100
    assert meta.title == long_hook


def test_metadata_description_includes_hook_cta_and_disclosure():
    draft = _draft()
    meta = _build_video_metadata(draft, _persona())
    assert draft.hook in meta.description
    assert draft.cta in meta.description
    assert "AI tools" in meta.description  # disclosure


def test_metadata_tags_include_brand_and_ai_shorts():
    meta = _build_video_metadata(_draft(), _persona(brand="Brand X"))
    assert "AI" in meta.tags
    assert "Shorts" in meta.tags
    assert "Brand X" in meta.tags


def test_metadata_tags_dedup():
    # AI/Shorts are added implicitly; if persona somehow had the same brand
    # twice we still want unique tags.
    meta = _build_video_metadata(_draft(), _persona(brand="AI"))
    assert meta.tags.count("AI") == 1


def test_metadata_tag_total_under_cap():
    meta = _build_video_metadata(_draft(), _persona())
    total_chars = sum(len(t) + 1 for t in meta.tags)
    assert total_chars <= YOUTUBE_TAG_TOTAL_CAP


def test_metadata_visibility_defaults_unlisted():
    meta = _build_video_metadata(_draft(), _persona())
    assert meta.visibility == Visibility.UNLISTED


def test_metadata_visibility_public():
    meta = _build_video_metadata(_draft(), _persona(), visibility=Visibility.PUBLIC)
    assert meta.visibility == Visibility.PUBLIC


def test_metadata_synthetic_media_flag_default_true():
    meta = _build_video_metadata(_draft(), _persona())
    assert meta.contains_synthetic_media is True
    assert meta.made_for_kids is False


def test_publisher_for_unknown_platform_raises():
    from shortstack_core.enums import Platform

    with pytest.raises(ValueError, match="no publisher implementation"):
        _publisher_for(Platform.IG_REELS)


def test_publish_task_is_registered():
    from shortstack_worker.tasks.publish import publish_video

    assert publish_video.name == "shortstack_worker.tasks.publish.publish_video"
