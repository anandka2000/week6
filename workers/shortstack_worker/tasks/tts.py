"""Phase 3 TTS slice: synthesize a single voiceover for a script.

  synthesize_voiceover(video_id, script_id) -> dict
    1. Loads the validated ScriptDraft + NichePersona.
    2. Composes one continuous narration string (scenes joined by ". ").
    3. Calls ElevenLabs once with the niche-pinned voice.
    4. Records the cost event, then enforces the per-video hard cap.
    5. Uploads voice.mp3 and inserts an Asset row.

Idempotent: if an audio_voice asset already exists for the script we
short-circuit and return its info rather than calling ElevenLabs again.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select

from shortstack_core.cost import (
    CostCapExceeded,
    check_video_cap,
    record_tts,
)
from shortstack_core.db import Asset, Niche, Script, session_scope
from shortstack_core.enums import AssetKind
from shortstack_core.schemas import NichePersona, ScriptDraft
from shortstack_core.settings import get_settings
from shortstack_core.storage import upload_bytes, video_key

from ..celery_app import app  # noqa: F401  (ensures app is registered)
from ..sources import elevenlabs

log = get_task_logger(__name__)

VOICE_ID_PLACEHOLDER = "REPLACE_WITH_ELEVENLABS_VOICE_ID"


def _compose_narration(draft: ScriptDraft) -> str:
    """Join all scene narrations into one TTS payload.

    Scenes are concatenated in ``index`` order with ``". "`` between them so
    ElevenLabs gets a natural pause between scenes. Scene 0 (the hook) is
    therefore the very first sentence of the result.
    """
    ordered = sorted(draft.scenes, key=lambda s: s.index)
    return ". ".join(scene.narration for scene in ordered)


@shared_task(
    name="shortstack_worker.tasks.tts.synthesize_voiceover",
    acks_late=True,
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    max_retries=3,
)
def synthesize_voiceover(video_id: str, script_id: str) -> dict[str, Any]:
    settings = get_settings()
    script_uuid = UUID(script_id)
    video_uuid = UUID(video_id)

    # 1) Idempotency check + load draft / persona inside a session.
    with session_scope() as s:
        existing = s.scalar(
            select(Asset).where(
                Asset.script_id == script_uuid,
                Asset.kind == AssetKind.AUDIO_VOICE,
            )
        )
        if existing is not None:
            log.info(
                "synthesize_voiceover.idempotent_hit",
                extra={"script_id": script_id, "asset_id": str(existing.id)},
            )
            return {
                "asset_id": str(existing.id),
                "s3_key": existing.s3_key,
                "characters": int(existing.meta.get("characters", 0)),
                "audio_format": "mp3",
            }

        script = s.get(Script, script_uuid)
        if script is None:
            raise ValueError(f"script {script_id} not found")
        niche = s.get(Niche, script.niche_id)
        if niche is None:
            raise ValueError(f"niche {script.niche_id} for script {script_id} not found")

        draft = ScriptDraft.model_validate(script.draft_json)
        persona = NichePersona.model_validate(niche.persona_json)
        niche_id = niche.id
        niche_slug = niche.slug
        cost_cap = niche.cost_cap_cents

    if persona.voice_id == VOICE_ID_PLACEHOLDER:
        raise ValueError(f"voice_id not configured for niche {niche_slug}")

    text = _compose_narration(draft)
    characters = len(text)

    # 2) Call ElevenLabs (outside the DB transaction).
    audio_bytes = elevenlabs.synthesize(
        text=text,
        voice_id=persona.voice_id,
        model_id=settings.elevenlabs_model,
    )

    # 3) Record cost + enforce hard cap before we persist any artifacts.
    with session_scope() as s:
        record_tts(
            s,
            niche_id=niche_id,
            model=settings.elevenlabs_model,
            characters=characters,
            video_id=video_uuid,
            meta={"task": "synthesize_voiceover"},
        )
        try:
            check_video_cap(s, video_id=video_uuid, hard_cap_cents=cost_cap)
        except CostCapExceeded:
            # Persist the cost event and re-raise so the orchestrator can mark
            # the video failed. Do NOT retry on this -- raising out of the
            # task without httpx.HTTPError keeps celery from retrying.
            raise

    # 4) Upload to S3 and insert the Asset row.
    s3_key = upload_bytes(
        video_key(video_id, "voice.mp3"),
        audio_bytes,
        content_type="audio/mpeg",
    )

    with session_scope() as s:
        asset = Asset(
            script_id=script_uuid,
            kind=AssetKind.AUDIO_VOICE,
            scene_index=None,
            provider="elevenlabs",
            s3_key=s3_key,
            meta={
                "characters": characters,
                "model": settings.elevenlabs_model,
                "voice_id": persona.voice_id,
            },
        )
        s.add(asset)
        s.flush()
        asset_id = str(asset.id)

    log.info(
        "synthesize_voiceover.done",
        extra={
            "script_id": script_id,
            "video_id": video_id,
            "asset_id": asset_id,
            "characters": characters,
            "s3_key": s3_key,
        },
    )

    return {
        "asset_id": asset_id,
        "s3_key": s3_key,
        "characters": characters,
        "audio_format": "mp3",
    }
