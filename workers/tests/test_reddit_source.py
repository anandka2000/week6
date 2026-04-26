"""Reddit fetcher tests with respx-mocked HTTP."""

from __future__ import annotations

import httpx
import pytest
import respx

from shortstack_core.enums import TrendSource
from shortstack_worker.sources.reddit import REDDIT_HOT_URL, fetch_subreddit_hot

SAMPLE_LISTING = {
    "kind": "Listing",
    "data": {
        "children": [
            {
                "kind": "t3",
                "data": {
                    "id": "abc123",
                    "title": "ChatGPT replaced my todo list and I shipped 14 features",
                    "url": "https://reddit.com/r/productivity/comments/abc123",
                    "selftext": "I tried this for 30 days...",
                    "score": 5421,
                    "subreddit": "productivity",
                },
            },
            {
                "kind": "t3",
                "data": {
                    "id": "def456",
                    "title": "Why most AI productivity tools are scams",
                    "url": "https://reddit.com/r/productivity/comments/def456",
                    "selftext": "",
                    "score": 1234,
                    "subreddit": "productivity",
                },
            },
        ]
    },
}


@respx.mock
def test_fetch_subreddit_hot_normalizes():
    respx.get(REDDIT_HOT_URL.format(sub="productivity")).mock(
        return_value=httpx.Response(200, json=SAMPLE_LISTING)
    )
    items = fetch_subreddit_hot("productivity", limit=25)
    assert len(items) == 2
    assert items[0].source is TrendSource.REDDIT
    assert items[0].external_id == "t3_abc123"
    assert items[0].title.startswith("ChatGPT")
    # selftext truncated to summary
    assert items[0].summary == "I tried this for 30 days..."
    # empty selftext becomes None
    assert items[1].summary is None


@respx.mock
def test_fetch_subreddit_hot_skips_missing_id():
    bad = {"data": {"children": [{"kind": "t3", "data": {"title": "no id here"}}]}}
    respx.get(REDDIT_HOT_URL.format(sub="x")).mock(
        return_value=httpx.Response(200, json=bad)
    )
    assert fetch_subreddit_hot("x") == []


@respx.mock
def test_fetch_subreddit_hot_raises_on_5xx():
    respx.get(REDDIT_HOT_URL.format(sub="oops")).mock(
        return_value=httpx.Response(503, json={})
    )
    with pytest.raises(httpx.HTTPStatusError):
        fetch_subreddit_hot("oops")
