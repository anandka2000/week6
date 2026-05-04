"""BufferPublisher unit tests. respx-mocked HTTP, no real network.

Covers:
  - happy path: upload-media -> updates/create -> PublicationResult
  - missing access token raises ValueError at construction
  - 4xx upstream wraps to PublishError
  - malformed (non-JSON / missing-id) responses raise PublishError
  - empty profile_id is rejected
"""

from __future__ import annotations

import httpx
import pytest
import respx

from shortstack_core.enums import Platform, Visibility
from shortstack_publishers import BufferPublisher, PublishError, VideoMetadata
from shortstack_publishers.buffer import (
    UPDATE_CREATE_URL_FMT,
    UPLOAD_MEDIA_URL,
)


def _set_buffer_env(monkeypatch, token: str = "buf-test-token"):
    monkeypatch.setenv("BUFFER_ACCESS_TOKEN", token)
    import shortstack_core.settings as st

    st._settings = None


def _clear_buffer_env(monkeypatch):
    monkeypatch.delenv("BUFFER_ACCESS_TOKEN", raising=False)
    import shortstack_core.settings as st

    st._settings = None


def _meta(visibility: Visibility = Visibility.UNLISTED) -> VideoMetadata:
    return VideoMetadata(
        title="Stop scrolling. This works.",
        description="Three seconds of friction is killing your focus.",
        tags=["AI", "Shorts"],
        visibility=visibility,
    )


def test_constructor_requires_profile_id(monkeypatch):
    _set_buffer_env(monkeypatch)
    with pytest.raises(ValueError, match="profile_id"):
        BufferPublisher(platform=Platform.IG_REELS, profile_id="")


def test_constructor_requires_access_token(monkeypatch):
    _clear_buffer_env(monkeypatch)
    with pytest.raises(ValueError, match="access token"):
        BufferPublisher(platform=Platform.IG_REELS, profile_id="prof-123")


def test_constructor_accepts_explicit_token(monkeypatch):
    # Even with no env var set, an explicit access_token argument is accepted.
    _clear_buffer_env(monkeypatch)
    pub = BufferPublisher(
        platform=Platform.TIKTOK,
        profile_id="prof-1",
        access_token="explicit-tok",
    )
    assert pub.platform is Platform.TIKTOK


@respx.mock
def test_publish_round_trip(monkeypatch):
    _set_buffer_env(monkeypatch)
    profile_id = "prof-ig-1"

    upload_route = respx.post(UPLOAD_MEDIA_URL).mock(
        return_value=httpx.Response(200, json={"media_id": "media-xyz"})
    )
    create_url = UPDATE_CREATE_URL_FMT.format(profile_id=profile_id)
    create_route = respx.post(create_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "updates": [
                    {
                        "id": "post-789",
                        "service_link": "https://instagram.com/reel/abc",
                    }
                ]
            },
        )
    )

    publisher = BufferPublisher(platform=Platform.IG_REELS, profile_id=profile_id)
    result = publisher.publish(b"\x00" * 1024, _meta())

    assert upload_route.called
    assert create_route.called
    assert result.platform is Platform.IG_REELS
    assert result.external_id == "post-789"
    assert "instagram.com/reel/abc" in str(result.external_url)
    assert result.visibility is Visibility.UNLISTED
    assert result.raw["updates"][0]["id"] == "post-789"


@respx.mock
def test_publish_falls_back_to_buffer_link_when_no_native_link(monkeypatch):
    _set_buffer_env(monkeypatch)
    profile_id = "prof-x-1"

    respx.post(UPLOAD_MEDIA_URL).mock(
        return_value=httpx.Response(200, json={"media_id": "m1"})
    )
    respx.post(UPDATE_CREATE_URL_FMT.format(profile_id=profile_id)).mock(
        return_value=httpx.Response(200, json={"updates": [{"id": "post-1"}]})
    )

    publisher = BufferPublisher(platform=Platform.X, profile_id=profile_id)
    result = publisher.publish(b"x", _meta())
    assert "buffer.com" in str(result.external_url)
    assert "post-1" in str(result.external_url)


@respx.mock
def test_publish_wraps_4xx_from_upload(monkeypatch):
    _set_buffer_env(monkeypatch)
    respx.post(UPLOAD_MEDIA_URL).mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )

    publisher = BufferPublisher(platform=Platform.IG_REELS, profile_id="prof-1")
    with pytest.raises(PublishError, match="401"):
        publisher.publish(b"x", _meta())


@respx.mock
def test_publish_wraps_4xx_from_create_update(monkeypatch):
    _set_buffer_env(monkeypatch)
    profile_id = "prof-tiktok"

    respx.post(UPLOAD_MEDIA_URL).mock(
        return_value=httpx.Response(200, json={"media_id": "media-1"})
    )
    respx.post(UPDATE_CREATE_URL_FMT.format(profile_id=profile_id)).mock(
        return_value=httpx.Response(422, text="invalid scheduled_at")
    )

    publisher = BufferPublisher(platform=Platform.TIKTOK, profile_id=profile_id)
    with pytest.raises(PublishError, match="422"):
        publisher.publish(b"x", _meta())


@respx.mock
def test_publish_handles_malformed_upload_response(monkeypatch):
    _set_buffer_env(monkeypatch)
    respx.post(UPLOAD_MEDIA_URL).mock(
        return_value=httpx.Response(200, text="<html>not json</html>")
    )

    publisher = BufferPublisher(platform=Platform.LINKEDIN, profile_id="prof-li")
    with pytest.raises(PublishError, match="not valid JSON"):
        publisher.publish(b"x", _meta())


@respx.mock
def test_publish_handles_upload_response_missing_media_id(monkeypatch):
    _set_buffer_env(monkeypatch)
    respx.post(UPLOAD_MEDIA_URL).mock(
        return_value=httpx.Response(200, json={"unrelated": "stuff"})
    )

    publisher = BufferPublisher(platform=Platform.IG_REELS, profile_id="prof-1")
    with pytest.raises(PublishError, match="media_id"):
        publisher.publish(b"x", _meta())


@respx.mock
def test_publish_handles_create_response_missing_post_id(monkeypatch):
    _set_buffer_env(monkeypatch)
    profile_id = "prof-1"
    respx.post(UPLOAD_MEDIA_URL).mock(
        return_value=httpx.Response(200, json={"media_id": "m"})
    )
    respx.post(UPDATE_CREATE_URL_FMT.format(profile_id=profile_id)).mock(
        return_value=httpx.Response(200, json={"updates": []})
    )

    publisher = BufferPublisher(platform=Platform.IG_REELS, profile_id=profile_id)
    with pytest.raises(PublishError, match="no post id"):
        publisher.publish(b"x", _meta())


@respx.mock
def test_publish_handles_malformed_create_response(monkeypatch):
    _set_buffer_env(monkeypatch)
    profile_id = "prof-1"
    respx.post(UPLOAD_MEDIA_URL).mock(
        return_value=httpx.Response(200, json={"media_id": "m"})
    )
    respx.post(UPDATE_CREATE_URL_FMT.format(profile_id=profile_id)).mock(
        return_value=httpx.Response(200, text="not-json")
    )

    publisher = BufferPublisher(platform=Platform.IG_REELS, profile_id=profile_id)
    with pytest.raises(PublishError, match="not valid JSON"):
        publisher.publish(b"x", _meta())
