"""Buffer publisher — fans one mp4 out to IG / TikTok / X / LinkedIn.

A single Buffer account binds many platform "profiles" (channels). One
``BufferPublisher`` instance is created per (platform, profile_id) pair —
the worker constructs it from ``NichePersona.buffer_profiles``.

Flow (Buffer Publishing API v2 — see "open questions" in PR description if
the live response shape diverges from what we mocked):

    1. POST ``https://api.buffer.com/2/upload-media`` with a multipart
       ``file`` field. Header ``Authorization: Bearer <access_token>``.
       Response: ``{"media_id": "<id>", ...}``.
    2. POST ``https://api.buffer.com/2/profiles/{profile_id}/updates/create.json``
       with JSON body ``{"text": <caption>, "media": {"media_id": <id>},
       "now": true}`` (or ``{"scheduled_at": <iso>}`` for queued posts).
       Response: ``{"updates": [{"id": "<post_id>", "service_link": "..."}],
       ...}``.

Errors are wrapped as ``PublishError(self.platform, ..., cause=...)`` so
the worker can treat all publishers uniformly.
"""

from __future__ import annotations

from typing import Any

import httpx

from shortstack_core.enums import Platform
from shortstack_core.schemas import PublicationResult
from shortstack_core.settings import get_settings

from .base import Publisher, PublishError, VideoMetadata

BUFFER_API_BASE = "https://api.buffer.com/2"
UPLOAD_MEDIA_URL = f"{BUFFER_API_BASE}/upload-media"
UPDATE_CREATE_URL_FMT = f"{BUFFER_API_BASE}/profiles/{{profile_id}}/updates/create.json"
BUFFER_FALLBACK_URL_FMT = "https://buffer.com/app/updates/{post_id}"


def _build_caption(meta: VideoMetadata) -> str:
    """Compose a caption from title + description. Buffer's per-platform
    truncation is left to Buffer; we only enforce a generous upper bound so
    we never POST a multi-megabyte string by accident."""
    parts: list[str] = [meta.title.strip()]
    desc = (meta.description or "").strip()
    if desc:
        parts.append(desc)
    if meta.tags:
        parts.append(" ".join(f"#{t.replace(' ', '')}" for t in meta.tags))
    return "\n\n".join(parts)[:5000]


class BufferPublisher(Publisher):
    """Publishes through Buffer to one downstream platform."""

    def __init__(
        self,
        *,
        platform: Platform,
        profile_id: str,
        access_token: str | None = None,
        client: httpx.Client | None = None,
    ):
        if not profile_id:
            raise ValueError("BufferPublisher requires a non-empty profile_id")
        self.platform = platform
        self._profile_id = profile_id
        s = get_settings()
        self._access_token = access_token if access_token is not None else s.buffer_access_token
        if not self._access_token:
            raise ValueError(
                "Buffer access token missing — set BUFFER_ACCESS_TOKEN or pass "
                "access_token explicitly"
            )
        # Conservative timeouts: media upload can be slow on a constrained box.
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(connect=10.0, read=600.0, write=600.0, pool=10.0)
        )

    # -- internals ---------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    def _upload_media(self, video_bytes: bytes) -> str:
        files = {"file": ("video.mp4", video_bytes, "video/mp4")}
        resp = self._client.post(
            UPLOAD_MEDIA_URL, headers=self._auth_headers(), files=files
        )
        resp.raise_for_status()
        try:
            payload = resp.json()
        except ValueError as exc:  # malformed JSON
            raise PublishError(
                self.platform,
                f"upload-media response is not valid JSON: {resp.text[:200]}",
                cause=exc,
            ) from exc
        media_id = payload.get("media_id") or payload.get("id")
        if not media_id:
            raise PublishError(
                self.platform,
                f"upload-media response missing media_id: {str(payload)[:200]}",
            )
        return media_id

    def _create_update(self, media_id: str, caption: str) -> dict[str, Any]:
        url = UPDATE_CREATE_URL_FMT.format(profile_id=self._profile_id)
        body = {
            "text": caption,
            "media": {"media_id": media_id},
            "now": True,
        }
        resp = self._client.post(url, headers=self._auth_headers(), json=body)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError as exc:
            raise PublishError(
                self.platform,
                f"updates/create response is not valid JSON: {resp.text[:200]}",
                cause=exc,
            ) from exc

    @staticmethod
    def _extract_post(payload: dict[str, Any]) -> tuple[str, str | None]:
        """Pull (post_id, native_link) out of an updates/create response."""
        updates = payload.get("updates") or []
        if not updates:
            return "", None
        first = updates[0] or {}
        post_id = first.get("id") or first.get("update_id") or ""
        native_link = (
            first.get("service_link")
            or first.get("permalink")
            or first.get("url")
        )
        return post_id, native_link

    # -- contract ----------------------------------------------------------

    def publish(
        self, video_bytes: bytes, metadata: VideoMetadata
    ) -> PublicationResult:
        try:
            media_id = self._upload_media(video_bytes)
            caption = _build_caption(metadata)
            response = self._create_update(media_id, caption)
        except PublishError:
            raise
        except httpx.HTTPStatusError as exc:
            raise PublishError(
                self.platform,
                f"{exc.response.status_code} {exc.response.text[:500]}",
                cause=exc,
            ) from exc
        except httpx.HTTPError as exc:
            raise PublishError(self.platform, str(exc), cause=exc) from exc

        post_id, native_link = self._extract_post(response)
        if not post_id:
            raise PublishError(
                self.platform,
                f"updates/create returned no post id: {str(response)[:200]}",
            )

        external_url = native_link or BUFFER_FALLBACK_URL_FMT.format(post_id=post_id)
        return PublicationResult(
            platform=self.platform,
            external_id=post_id,
            external_url=external_url,
            visibility=metadata.visibility,
            raw=response,
        )
