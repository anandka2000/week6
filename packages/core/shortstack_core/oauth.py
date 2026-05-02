"""Google OAuth refresh-token helper.

Shared by ``shortstack_publishers.youtube`` (upload) and
``shortstack_worker.sources.youtube_analytics`` (read). The access token is
cached at module level for ~50 minutes so multiple API calls within one
worker task share a single OAuth round-trip.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from .settings import get_settings

OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105


@dataclass
class _TokenCache:
    token: str
    expires_at: float


_cache: _TokenCache | None = None


def google_access_token(
    *,
    client: httpx.Client | None = None,
    force_refresh: bool = False,
) -> str:
    """Return a fresh Google access token. Cached in-memory until expiry."""
    global _cache
    s = get_settings()
    if not (
        s.youtube_oauth_client_id
        and s.youtube_oauth_client_secret
        and s.youtube_oauth_refresh_token
    ):
        raise ValueError(
            "Google OAuth credentials missing — set "
            "YOUTUBE_OAUTH_CLIENT_ID / YOUTUBE_OAUTH_CLIENT_SECRET / YOUTUBE_OAUTH_REFRESH_TOKEN"
        )

    now = time.time()
    if not force_refresh and _cache is not None and _cache.expires_at > now + 60:
        return _cache.token

    owns = client is None
    client = client or httpx.Client(timeout=30.0)
    try:
        resp = client.post(
            OAUTH_TOKEN_URL,
            data={
                "client_id": s.youtube_oauth_client_id,
                "client_secret": s.youtube_oauth_client_secret,
                "refresh_token": s.youtube_oauth_refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    finally:
        if owns:
            client.close()

    token = data.get("access_token")
    expires_in = int(data.get("expires_in", 3599))
    if not token:
        raise RuntimeError(f"OAuth response missing access_token: {data}")
    _cache = _TokenCache(token=token, expires_at=now + expires_in)
    return token


def reset_token_cache() -> None:
    """Test hook. Clears the in-memory cache."""
    global _cache
    _cache = None
