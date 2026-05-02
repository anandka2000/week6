"""YouTubeShortsPublisher unit tests. respx-mocked HTTP, no real network."""

from __future__ import annotations

import httpx
import pytest
import respx

from shortstack_core.enums import Platform, Visibility
from shortstack_publishers import (
    PublishError,
    VideoMetadata,
    YouTubeShortsPublisher,
)
from shortstack_publishers.youtube import (
    OAUTH_TOKEN_URL,
    UPLOAD_BASE_URL,
    _build_youtube_body,
)


def _set_oauth_env(monkeypatch):
    monkeypatch.setenv("YOUTUBE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("YOUTUBE_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("YOUTUBE_OAUTH_REFRESH_TOKEN", "test-refresh-token")
    # reset the cached settings singleton
    import shortstack_core.settings as st

    st._settings = None


def test_build_youtube_body_shape():
    """Map VideoMetadata to YouTube's API shape correctly."""
    meta = VideoMetadata(
        title="Stop scrolling. This works.",
        description="Three seconds of friction is killing your focus.\n\nFollow.",
        tags=["AI", "Shorts", "productivity"],
        visibility=Visibility.UNLISTED,
        category_id="28",
        contains_synthetic_media=True,
        made_for_kids=False,
    )
    body = _build_youtube_body(meta)
    assert body["snippet"]["title"] == "Stop scrolling. This works."
    assert body["snippet"]["categoryId"] == "28"
    assert body["snippet"]["tags"] == ["AI", "Shorts", "productivity"]
    assert body["status"]["privacyStatus"] == "unlisted"
    assert body["status"]["selfDeclaredMadeForKids"] is False
    assert body["status"]["containsSyntheticMedia"] is True


def test_build_youtube_body_public_visibility():
    meta = VideoMetadata(title="x", visibility=Visibility.PUBLIC)
    assert _build_youtube_body(meta)["status"]["privacyStatus"] == "public"


def test_publisher_requires_credentials():
    import shortstack_core.settings as st

    st._settings = None
    # No env set - constructor should refuse.
    with pytest.raises(ValueError, match="OAuth credentials missing"):
        YouTubeShortsPublisher(client_id="", client_secret="", refresh_token="")


@respx.mock
def test_publisher_round_trip(monkeypatch):
    _set_oauth_env(monkeypatch)

    upload_session_url = (
        "https://upload.googleapis.com/upload/youtube/v3/videos?upload_id=test-session"
    )

    oauth_route = respx.post(OAUTH_TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "tok-abc", "expires_in": 3599, "token_type": "Bearer"},
        )
    )
    start_route = respx.post(UPLOAD_BASE_URL).mock(
        return_value=httpx.Response(200, headers={"Location": upload_session_url})
    )
    put_route = respx.put(upload_session_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "yt-video-id-xyz",
                "kind": "youtube#video",
                "snippet": {"title": "x"},
            },
        )
    )

    publisher = YouTubeShortsPublisher()
    metadata = VideoMetadata(
        title="My short",
        description="hi",
        tags=["AI", "Shorts"],
        visibility=Visibility.UNLISTED,
    )
    result = publisher.publish(b"\x00" * 4096, metadata)

    assert oauth_route.called
    assert start_route.called
    assert put_route.called
    assert result.platform == Platform.YOUTUBE_SHORTS
    assert result.external_id == "yt-video-id-xyz"
    assert "yt-video-id-xyz" in str(result.external_url)
    assert result.visibility == Visibility.UNLISTED
    assert result.raw["id"] == "yt-video-id-xyz"


@respx.mock
def test_publisher_wraps_oauth_failure(monkeypatch):
    _set_oauth_env(monkeypatch)
    respx.post(OAUTH_TOKEN_URL).mock(
        return_value=httpx.Response(401, json={"error": "invalid_grant"})
    )

    publisher = YouTubeShortsPublisher()
    with pytest.raises(PublishError, match="401"):
        publisher.publish(b"x", VideoMetadata(title="hi"))


@respx.mock
def test_publisher_missing_location_header(monkeypatch):
    _set_oauth_env(monkeypatch)
    respx.post(OAUTH_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok"})
    )
    respx.post(UPLOAD_BASE_URL).mock(return_value=httpx.Response(200, json={}))

    publisher = YouTubeShortsPublisher()
    with pytest.raises(PublishError, match="Location"):
        publisher.publish(b"x", VideoMetadata(title="hi"))


@respx.mock
def test_publisher_upload_returns_no_id(monkeypatch):
    _set_oauth_env(monkeypatch)
    upload_url = "https://example.com/upload-here"

    respx.post(OAUTH_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok"})
    )
    respx.post(UPLOAD_BASE_URL).mock(
        return_value=httpx.Response(200, headers={"Location": upload_url})
    )
    respx.put(upload_url).mock(
        return_value=httpx.Response(200, json={"kind": "youtube#video"})  # no id
    )

    publisher = YouTubeShortsPublisher()
    with pytest.raises(PublishError, match="no id"):
        publisher.publish(b"x", VideoMetadata(title="hi"))
