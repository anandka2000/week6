"""ElevenLabs TTS fetcher tests with respx-mocked HTTP."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from shortstack_worker.sources.elevenlabs import ELEVENLABS_TTS_URL, synthesize


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    """Force the ElevenLabs settings used by the source under test."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_MODEL", "eleven_turbo_v2_5")
    import shortstack_core.settings as st

    st._settings = None
    yield
    st._settings = None


@respx.mock
def test_synthesize_happy_returns_bytes():
    fake_mp3 = b"ID3\x03\x00\x00\x00fake-mp3-bytes"
    route = respx.post(ELEVENLABS_TTS_URL.format(voice_id="vox-1")).mock(
        return_value=httpx.Response(200, content=fake_mp3),
    )

    out = synthesize("hello world", voice_id="vox-1")

    assert out == fake_mp3
    assert route.called


@respx.mock
def test_synthesize_sends_correct_url_headers_body():
    seen: list[httpx.Request] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"ok")

    respx.post(ELEVENLABS_TTS_URL.format(voice_id="vox-9")).mock(side_effect=_capture)

    synthesize("the quick brown fox", voice_id="vox-9", model_id="eleven_turbo_v2_5")

    assert len(seen) == 1
    req = seen[0]
    assert req.url.path == "/v1/text-to-speech/vox-9"
    assert req.headers["xi-api-key"] == "test-key"
    assert req.headers["accept"] == "audio/mpeg"
    assert req.headers["content-type"].startswith("application/json")

    body = json.loads(req.content)
    assert body["text"] == "the quick brown fox"
    assert body["model_id"] == "eleven_turbo_v2_5"
    assert body["voice_settings"] == {"stability": 0.5, "similarity_boost": 0.75}


@respx.mock
def test_synthesize_defaults_model_from_settings():
    seen: list[httpx.Request] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"ok")

    respx.post(ELEVENLABS_TTS_URL.format(voice_id="vox-1")).mock(side_effect=_capture)

    synthesize("hi", voice_id="vox-1")

    body = json.loads(seen[0].content)
    assert body["model_id"] == "eleven_turbo_v2_5"


@respx.mock
def test_synthesize_raises_on_4xx():
    respx.post(ELEVENLABS_TTS_URL.format(voice_id="vox-bad")).mock(
        return_value=httpx.Response(401, json={"detail": "bad key"}),
    )
    with pytest.raises(httpx.HTTPStatusError):
        synthesize("hi", voice_id="vox-bad")


@respx.mock
def test_synthesize_raises_on_5xx():
    respx.post(ELEVENLABS_TTS_URL.format(voice_id="vox-down")).mock(
        return_value=httpx.Response(503, json={}),
    )
    with pytest.raises(httpx.HTTPStatusError):
        synthesize("hi", voice_id="vox-down")
