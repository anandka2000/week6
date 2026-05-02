"""ElevenLabs text-to-speech source.

Wraps the ``/v1/text-to-speech/{voice_id}`` endpoint. Returns raw mp3 bytes
so the caller can upload them to S3 unchanged. The TTS endpoint can be slow
on long narrations, so we use a generous 60s timeout.
"""

from __future__ import annotations

import httpx

from shortstack_core.settings import get_settings

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def synthesize(
    text: str,
    *,
    voice_id: str,
    model_id: str | None = None,
    client: httpx.Client | None = None,
) -> bytes:
    """Synthesize ``text`` into mp3 bytes via ElevenLabs.

    Raises ``httpx.HTTPStatusError`` on 4xx/5xx so the celery task can
    autoretry on transient failures.
    """
    settings = get_settings()
    chosen_model = model_id or settings.elevenlabs_model

    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    body = {
        "text": text,
        "model_id": chosen_model,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    owns_client = client is None
    client = client or httpx.Client(timeout=60.0)
    try:
        resp = client.post(
            ELEVENLABS_TTS_URL.format(voice_id=voice_id),
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        return resp.content
    finally:
        if owns_client:
            client.close()
