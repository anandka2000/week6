"""Pexels stock-photo source.

Thin wrapper around the v1 search endpoint. The visual_prompt produced by
Sonnet is already noun-first and concrete, so we pass it straight through
as ``query`` rather than re-extracting keywords.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from shortstack_core.settings import get_settings

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"


@dataclass(frozen=True)
class PexelsPhoto:
    id: int
    page_url: str
    src_portrait: str
    alt: str


def search_photos(
    query: str,
    *,
    per_page: int = 5,
    client: httpx.Client | None = None,
) -> list[PexelsPhoto]:
    """Search Pexels for portrait (9:16) photos matching ``query``.

    Returns an empty list when Pexels has no hits. Skips entries missing the
    fields we need to display or download a candidate.
    """
    settings = get_settings()
    headers = {"Authorization": settings.pexels_api_key}

    owns_client = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        resp = client.get(
            PEXELS_SEARCH_URL,
            params={"query": query, "per_page": per_page, "orientation": "portrait"},
            headers=headers,
        )
        resp.raise_for_status()
        payload = resp.json()
    finally:
        if owns_client:
            client.close()

    photos: list[PexelsPhoto] = []
    for entry in payload.get("photos", []) or []:
        photo_id = entry.get("id")
        page_url = entry.get("url")
        src = (entry.get("src") or {}).get("portrait")
        alt = entry.get("alt") or ""
        if photo_id is None or not page_url or not src:
            continue
        photos.append(
            PexelsPhoto(
                id=int(photo_id),
                page_url=page_url,
                src_portrait=src,
                alt=alt,
            )
        )
    return photos


def download_photo(src_url: str, *, client: httpx.Client | None = None) -> bytes:
    """Fetch the raw bytes of a Pexels image (any size). No auth required for
    image CDN URLs returned by the search API.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        resp = client.get(src_url)
        resp.raise_for_status()
        return resp.content
    finally:
        if owns_client:
            client.close()
