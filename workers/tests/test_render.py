"""Phase 4 render task — pure-helper tests. DB / S3 / Remotion paths deferred."""

from __future__ import annotations

from unittest.mock import patch

from shortstack_core.schemas import (
    AssetRef,
    CaptionsDoc,
    Scene,
    ScriptDraft,
    Word,
)
from shortstack_worker.tasks.render import _build_render_request


def _draft() -> ScriptDraft:
    return ScriptDraft(
        hook="Stop scrolling. This one tool runs my whole week.",
        scenes=[
            Scene(
                index=0,
                narration="Stop scrolling.",
                on_screen_text="STOP",
                visual_prompt="dramatic close-up",
                duration_sec=2.5,
            ),
            Scene(
                index=1,
                narration="One tool. Whole week. No exceptions.",
                on_screen_text="",
                visual_prompt="desk overhead shot",
                duration_sec=4.0,
            ),
            Scene(
                index=2,
                narration="Here is exactly what I do.",
                on_screen_text="THE PLAY",
                visual_prompt="hands on keyboard",
                duration_sec=4.0,
            ),
            Scene(
                index=3,
                narration="Steal it before everyone else does.",
                on_screen_text="",
                visual_prompt="phone on a table",
                duration_sec=4.0,
            ),
        ],
        cta="Follow if you want this in your inbox weekly.",
        total_duration_sec=14.5,
        prompt_version="scripts_v1",
        model="claude-sonnet-4-6",
    )


def _captions() -> CaptionsDoc:
    return CaptionsDoc(
        words=[
            Word(text="Stop", start=0.0, end=0.3),
            Word(text="scrolling.", start=0.3, end=0.9),
            Word(text="This", start=0.9, end=1.1),
        ]
    )


def test_build_render_request_shape():
    """The request body matches the contract the render service expects."""
    draft = _draft()
    captions = _captions()
    scene_keys = {
        0: "videos/abc/scene_0.png",
        1: "videos/abc/scene_1.jpg",
        2: "videos/abc/scene_2.png",
        3: "videos/abc/scene_3.jpg",
    }

    with patch("shortstack_worker.tasks.render.signed_url") as mock_signed:
        mock_signed.side_effect = lambda key, **_: f"https://signed/{key}"
        body = _build_render_request(
            video_id="vid-123",
            draft=draft,
            scene_image_keys=scene_keys,
            audio_key="videos/abc/voice.mp3",
            captions=captions,
        )

    assert body["video_id"] == "vid-123"
    assert body["cta"].startswith("Follow")
    assert body["total_duration_sec"] == 14.5
    assert len(body["scenes"]) == 4
    assert body["scenes"][0]["index"] == 0
    assert body["scenes"][0]["image_url"] == "https://signed/videos/abc/scene_0.png"
    assert body["scenes"][0]["duration_sec"] == 2.5
    assert body["scenes"][0]["on_screen_text"] == "STOP"
    assert body["audio_url"] == "https://signed/videos/abc/voice.mp3"
    # Captions are flattened to plain dicts (the render service is plain JS, not pydantic).
    assert body["captions"][0] == {"text": "Stop", "start": 0.0, "end": 0.3}


def test_build_render_request_uses_one_signed_url_per_scene_plus_audio():
    """Sanity: we only sign N+1 URLs (N scenes + audio), no extras."""
    draft = _draft()
    scene_keys = {i: f"videos/x/s_{i}.png" for i in range(len(draft.scenes))}

    with patch("shortstack_worker.tasks.render.signed_url") as mock_signed:
        mock_signed.side_effect = lambda key, **_: f"u://{key}"
        _build_render_request(
            video_id="x",
            draft=draft,
            scene_image_keys=scene_keys,
            audio_key="videos/x/voice.mp3",
            captions=_captions(),
        )
        assert mock_signed.call_count == len(draft.scenes) + 1


def test_render_task_is_registered():
    from shortstack_worker.tasks.render import render_video

    assert render_video.name == "shortstack_worker.tasks.render.render_video"


def test_asset_ref_kind_used_in_filtering():
    """The task filters Asset rows by kind. Confirm the enum values match."""
    from shortstack_core.enums import AssetKind

    img = AssetRef(
        kind=AssetKind.IMAGE,
        scene_index=0,
        provider="flux-schnell",
        s3_key="videos/x/scene_0.png",
    )
    voice = AssetRef(
        kind=AssetKind.AUDIO_VOICE,
        provider="elevenlabs",
        s3_key="videos/x/voice.mp3",
    )
    caps = AssetRef(
        kind=AssetKind.CAPTIONS_JSON,
        provider="whisper",
        s3_key="videos/x/captions.json",
    )
    assert img.kind == AssetKind.IMAGE
    assert voice.kind == AssetKind.AUDIO_VOICE
    assert caps.kind == AssetKind.CAPTIONS_JSON
