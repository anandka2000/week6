"""YouTube Data API v3 stats fetcher.

We use the public ``videos.list`` endpoint with ``part=statistics`` to get
view / like / comment counts. That's all the Data API exposes — for
average-view-duration, retention curve, and CTR we'd need the YouTube
*Analytics* API (different endpoint, different scope), which is on the
TODO list and not wired in v0.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from shortstack_core.oauth import google_access_token

VIDEOS_LIST_URL = "https://www.googleapis.com/youtube/v3/videos"


@dataclass(frozen=True)
class VideoStats:
    views: int
    likes: int
    comments: int


def fetch_video_stats(
    external_id: str,
    *,
    client: httpx.Client | None = None,
) -> VideoStats | None:
    """Look up basic stats for a YouTube video. Returns None if the id is
    unknown / private / deleted."""
    token = google_access_token(client=client)

    owns = client is None
    client = client or httpx.Client(timeout=30.0)
    try:
        resp = client.get(
            VIDEOS_LIST_URL,
            params={"part": "statistics", "id": external_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return None
        stats = items[0].get("statistics", {})
        return VideoStats(
            views=int(stats.get("viewCount", 0)),
            likes=int(stats.get("likeCount", 0)),
            comments=int(stats.get("commentCount", 0)),
        )
    finally:
        if owns:
            client.close()
