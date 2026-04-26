"""Reddit trends source.

v0 uses the public ``/r/<sub>/hot.json`` endpoint with a polite User-Agent.
Migrate to PRAW + OAuth (TODO) for higher rate limits when we hit them.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from shortstack_core.enums import TrendSource
from shortstack_core.schemas import TrendItem
from shortstack_core.settings import get_settings

REDDIT_HOT_URL = "https://www.reddit.com/r/{sub}/hot.json"


def fetch_subreddit_hot(
    subreddit: str,
    *,
    limit: int = 25,
    client: httpx.Client | None = None,
) -> list[TrendItem]:
    """Pull hot posts from a subreddit and normalize to ``TrendItem``."""
    settings = get_settings()
    headers = {"User-Agent": settings.reddit_user_agent}

    owns_client = client is None
    client = client or httpx.Client(timeout=15.0, headers=headers)
    try:
        resp = client.get(REDDIT_HOT_URL.format(sub=subreddit), params={"limit": limit})
        resp.raise_for_status()
        payload = resp.json()
    finally:
        if owns_client:
            client.close()

    now = datetime.now(tz=timezone.utc)
    items: list[TrendItem] = []
    for child in payload.get("data", {}).get("children", []):
        d = child.get("data", {})
        post_id = d.get("id")
        if not post_id:
            continue
        items.append(
            TrendItem(
                source=TrendSource.REDDIT,
                external_id=f"t3_{post_id}",
                title=d.get("title", ""),
                url=d.get("url"),
                summary=(d.get("selftext") or "")[:500] or None,
                raw=d,
                fetched_at=now,
            )
        )
    return items
