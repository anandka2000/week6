"""YouTube Shorts publisher via Data API v3 + OAuth refresh-token.

Flow:
    1. Exchange the long-lived refresh_token for a short-lived access_token.
    2. POST snippet+status to ``/upload/youtube/v3/videos?uploadType=resumable``;
       the response carries the upload session URL in the ``Location`` header.
    3. PUT the mp4 bytes to that session URL. The response is the YouTube
       video resource (we only need ``id``).

We use httpx directly rather than google-api-python-client to keep the
dep light and the wire calls easy to mock in tests. If we hit edge cases
(chunked resumes, quota retry semantics) we can swap in the official
client later.
"""

from __future__ import annotations

from typing import Any

import httpx

from shortstack_core.enums import Platform, Visibility
from shortstack_core.schemas import PublicationResult
from shortstack_core.settings import get_settings

from .base import Publisher, PublishError, VideoMetadata

OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_BASE_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
WATCH_URL_FMT = "https://youtube.com/shorts/{video_id}"

_VISIBILITY_MAP: dict[Visibility, str] = {
    Visibility.UNLISTED: "unlisted",
    Visibility.PUBLIC: "public",
}


def _build_youtube_body(meta: VideoMetadata) -> dict[str, Any]:
    """Map the platform-agnostic ``VideoMetadata`` to YouTube's API shape.

    Pure function so tests don't need to spin up the publisher.
    """
    return {
        "snippet": {
            "title": meta.title,
            "description": meta.description,
            "tags": meta.tags,
            "categoryId": meta.category_id,
        },
        "status": {
            "privacyStatus": _VISIBILITY_MAP[meta.visibility],
            "selfDeclaredMadeForKids": meta.made_for_kids,
            "containsSyntheticMedia": meta.contains_synthetic_media,
        },
    }


class YouTubeShortsPublisher(Publisher):
    platform = Platform.YOUTUBE_SHORTS

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        refresh_token: str | None = None,
        client: httpx.Client | None = None,
    ):
        s = get_settings()
        self._client_id = client_id or s.youtube_oauth_client_id
        self._client_secret = client_secret or s.youtube_oauth_client_secret
        self._refresh_token = refresh_token or s.youtube_oauth_refresh_token
        if not (self._client_id and self._client_secret and self._refresh_token):
            raise ValueError(
                "YouTube OAuth credentials missing — set YOUTUBE_OAUTH_CLIENT_ID / "
                "YOUTUBE_OAUTH_CLIENT_SECRET / YOUTUBE_OAUTH_REFRESH_TOKEN"
            )
        # 5min for OAuth, 5min for the resumable POST, 10min for the bytes PUT.
        self._client = client or httpx.Client(timeout=httpx.Timeout(connect=10.0, read=600.0, write=600.0, pool=10.0))

    def _access_token(self) -> str:
        resp = self._client.post(
            OAUTH_TOKEN_URL,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise PublishError(
                self.platform, f"oauth response missing access_token: {resp.text[:200]}"
            )
        return token

    def _start_resumable_upload(self, access_token: str, body: dict[str, Any]) -> str:
        resp = self._client.post(
            UPLOAD_BASE_URL,
            params={"part": "snippet,status", "uploadType": "resumable"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/mp4",
            },
            json=body,
        )
        resp.raise_for_status()
        location = resp.headers.get("Location") or resp.headers.get("location")
        if not location:
            raise PublishError(
                self.platform, "resumable upload response missing Location header"
            )
        return location

    def _put_bytes(self, upload_url: str, video_bytes: bytes) -> dict[str, Any]:
        resp = self._client.put(
            upload_url,
            content=video_bytes,
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(len(video_bytes)),
            },
        )
        resp.raise_for_status()
        return resp.json()

    def publish(
        self, video_bytes: bytes, metadata: VideoMetadata
    ) -> PublicationResult:
        try:
            access_token = self._access_token()
            body = _build_youtube_body(metadata)
            upload_url = self._start_resumable_upload(access_token, body)
            result = self._put_bytes(upload_url, video_bytes)
        except httpx.HTTPStatusError as exc:
            raise PublishError(
                self.platform,
                f"{exc.response.status_code} {exc.response.text[:500]}",
                cause=exc,
            ) from exc
        except httpx.HTTPError as exc:
            raise PublishError(self.platform, str(exc), cause=exc) from exc

        external_id = result.get("id")
        if not external_id:
            raise PublishError(
                self.platform, f"upload returned no id: {str(result)[:200]}"
            )

        return PublicationResult(
            platform=self.platform,
            external_id=external_id,
            external_url=WATCH_URL_FMT.format(video_id=external_id),
            visibility=metadata.visibility,
            raw=result,
        )
