"""Phase 3: caption generation via faster-whisper.

  transcribe_audio(video_id, audio_asset_id) -> downloads the voice asset, runs
                                                whisper word-timestamps, persists
                                                a CaptionsDoc JSON to S3, and
                                                inserts an Asset(captions_json).

The whisper model is lazily loaded once per process via ``get_whisper_model``
so subsequent task runs reuse the same handle.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable
from functools import lru_cache
from typing import Any
from uuid import UUID

import httpx
from celery import shared_task
from celery.utils.log import get_task_logger

from shortstack_core.db import Asset, session_scope
from shortstack_core.enums import AssetKind
from shortstack_core.schemas import CaptionsDoc, Word
from shortstack_core.storage import download_bytes, upload_bytes, video_key

from ..celery_app import app  # noqa: F401  (ensures app is registered)

log = get_task_logger(__name__)

WHISPER_MODEL_NAME = "base.en"


@lru_cache(maxsize=2)
def get_whisper_model(name: str) -> Any:
    """Lazy module-level cache for the faster-whisper model.

    Imported inside the function so unit tests can patch the ``faster_whisper``
    module at the import boundary without instantiating a real model.
    """
    from faster_whisper import WhisperModel

    return WhisperModel(name, device="cpu", compute_type="int8")


def _words_from_segments(segments: Iterable[Any]) -> list[Word]:
    """Convert faster-whisper segments into a flat list of ``Word``.

    Each segment exposes a ``.words`` iterable of objects with ``.word``,
    ``.start`` and ``.end`` attributes. Segments without word-level timing
    (``.words is None``) are skipped.
    """
    words: list[Word] = []
    for seg in segments:
        seg_words = getattr(seg, "words", None) or []
        for w in seg_words:
            words.append(
                Word(
                    text=w.word,
                    start=float(w.start),
                    end=float(w.end),
                )
            )
    return words


@shared_task(
    name="shortstack_worker.tasks.captions.transcribe_audio",
    acks_late=True,
    # Only retry transient failures: HTTP errors talking to S3, OS-level
    # errors writing the tempfile, and faster-whisper's RuntimeError on
    # transient model-load failure. ValueError indicates a contract
    # violation (e.g. wrong asset kind) and must NOT be retried.
    autoretry_for=(httpx.HTTPError, OSError, RuntimeError),
    retry_backoff=True,
    max_retries=2,
)
def transcribe_audio(video_id: str, audio_asset_id: str) -> dict[str, Any]:
    audio_uuid = UUID(audio_asset_id)

    # 1. Look up the audio asset and short-circuit if captions already exist.
    with session_scope() as s:
        audio = s.get(Asset, audio_uuid)
        if audio is None:
            raise ValueError(f"audio asset {audio_asset_id} not found")
        if audio.kind != AssetKind.AUDIO_VOICE:
            raise ValueError(
                f"asset {audio_asset_id} is {audio.kind.value!r}, expected audio_voice"
            )
        script_id = audio.script_id
        audio_s3_key = audio.s3_key

        existing = (
            s.query(Asset)
            .filter(
                Asset.script_id == script_id,
                Asset.kind == AssetKind.CAPTIONS_JSON,
            )
            .one_or_none()
        )
        if existing is not None:
            log.info(
                "transcribe_audio.idempotent_skip",
                extra={
                    "video_id": video_id,
                    "audio_asset_id": audio_asset_id,
                    "captions_asset_id": str(existing.id),
                },
            )
            return {
                "asset_id": str(existing.id),
                "s3_key": existing.s3_key,
                "n_words": int(existing.meta.get("n_words", 0)),
            }

    # 2. Download the audio bytes to a tempfile so faster-whisper can mmap it.
    audio_bytes = download_bytes(audio_s3_key)

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_path = tmp.name
    try:
        try:
            tmp.write(audio_bytes)
        finally:
            tmp.close()

        # 3. Transcribe with word timestamps.
        model = get_whisper_model(WHISPER_MODEL_NAME)
        segments, info = model.transcribe(tmp_path, word_timestamps=True)
        words = _words_from_segments(segments)
        captions_doc = CaptionsDoc(words=words)
        duration_sec = float(getattr(info, "duration", 0.0) or 0.0)
    finally:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass

    # 4. Upload the JSON document.
    s3_key = video_key(video_id, "captions.json")
    upload_bytes(
        s3_key,
        captions_doc.model_dump_json().encode("utf-8"),
        content_type="application/json",
    )

    # 5. Insert the Asset row.
    with session_scope() as s:
        asset = Asset(
            script_id=script_id,
            kind=AssetKind.CAPTIONS_JSON,
            scene_index=None,
            provider="whisper",
            s3_key=s3_key,
            meta={
                "n_words": len(words),
                "model": WHISPER_MODEL_NAME,
                "duration_sec": duration_sec,
            },
        )
        s.add(asset)
        s.flush()
        asset_id = str(asset.id)

    log.info(
        "transcribe_audio.ok",
        extra={
            "video_id": video_id,
            "audio_asset_id": audio_asset_id,
            "asset_id": asset_id,
            "n_words": len(words),
            "duration_sec": duration_sec,
        },
    )
    return {"asset_id": asset_id, "s3_key": s3_key, "n_words": len(words)}
