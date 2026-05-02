"""YouTube Data API stats fetcher tests."""

from __future__ import annotations

import httpx
import respx

from shortstack_core.oauth import OAUTH_TOKEN_URL, reset_token_cache
from shortstack_worker.sources.youtube_analytics import (
    VIDEOS_LIST_URL,
    VideoStats,
    fetch_video_stats,
)


def _set_oauth_env(monkeypatch):
    monkeypatch.setenv("YOUTUBE_OAUTH_CLIENT_ID", "c")
    monkeypatch.setenv("YOUTUBE_OAUTH_CLIENT_SECRET", "s")
    monkeypatch.setenv("YOUTUBE_OAUTH_REFRESH_TOKEN", "r")
    import shortstack_core.settings as st

    st._settings = None
    reset_token_cache()


def _oauth_route():
    return respx.post(OAUTH_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3599})
    )


@respx.mock
def test_fetch_video_stats_happy(monkeypatch):
    _set_oauth_env(monkeypatch)
    _oauth_route()
    respx.get(VIDEOS_LIST_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "vid-xyz",
                        "statistics": {
                            "viewCount": "1234",
                            "likeCount": "56",
                            "commentCount": "7",
                        },
                    }
                ]
            },
        )
    )
    stats = fetch_video_stats("vid-xyz")
    assert isinstance(stats, VideoStats)
    assert stats.views == 1234
    assert stats.likes == 56
    assert stats.comments == 7


@respx.mock
def test_fetch_video_stats_unknown_id_returns_none(monkeypatch):
    _set_oauth_env(monkeypatch)
    _oauth_route()
    respx.get(VIDEOS_LIST_URL).mock(return_value=httpx.Response(200, json={"items": []}))
    assert fetch_video_stats("nope") is None


@respx.mock
def test_fetch_video_stats_handles_missing_keys(monkeypatch):
    """YouTube returns the statistics object minus fields the channel hides."""
    _set_oauth_env(monkeypatch)
    _oauth_route()
    respx.get(VIDEOS_LIST_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [{"id": "x", "statistics": {"viewCount": "10"}}],
            },
        )
    )
    stats = fetch_video_stats("x")
    assert stats == VideoStats(views=10, likes=0, comments=0)
