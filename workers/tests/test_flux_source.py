"""Replicate / Flux Schnell source tests with respx-mocked HTTP."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from shortstack_worker.sources.flux import (
    REPLICATE_PREDICT_URL,
    FluxGenerationError,
    generate_image,
)


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    """Force the Replicate token used by the source under test."""
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-replicate-token")
    import shortstack_core.settings as st

    st._settings = None
    yield
    st._settings = None


POLL_URL = "https://api.replicate.com/v1/predictions/abc123"
OUTPUT_URL = "https://replicate.delivery/pbxt/abc/output.png"


@respx.mock
def test_generate_image_happy_path(monkeypatch):
    # Skip the real sleep when we have to poll.
    monkeypatch.setattr("shortstack_worker.sources.flux.time.sleep", lambda _s: None)

    seen_create: list[httpx.Request] = []

    def _capture_create(request: httpx.Request) -> httpx.Response:
        seen_create.append(request)
        return httpx.Response(
            201,
            json={
                "id": "abc123",
                "status": "starting",
                "urls": {"get": POLL_URL},
            },
        )

    respx.post(REPLICATE_PREDICT_URL).mock(side_effect=_capture_create)
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(
            200,
            json={"id": "abc123", "status": "succeeded", "output": [OUTPUT_URL]},
        )
    )
    fake_png = b"\x89PNGfakebytes"
    respx.get(OUTPUT_URL).mock(return_value=httpx.Response(200, content=fake_png))

    out = generate_image("a hand on a phone", aspect_ratio="9:16")
    assert out == fake_png

    # Verify request shape.
    assert len(seen_create) == 1
    req = seen_create[0]
    assert req.headers["authorization"] == "Token test-replicate-token"
    body = json.loads(req.content)
    assert body["input"]["prompt"] == "a hand on a phone"
    assert body["input"]["aspect_ratio"] == "9:16"
    assert body["input"]["num_outputs"] == 1
    assert body["input"]["output_format"] == "png"


@respx.mock
def test_generate_image_succeeds_immediately_without_polling(monkeypatch):
    """If create returns status=succeeded straight away we shouldn't poll."""
    monkeypatch.setattr("shortstack_worker.sources.flux.time.sleep", lambda _s: None)

    respx.post(REPLICATE_PREDICT_URL).mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "abc123",
                "status": "succeeded",
                "urls": {"get": POLL_URL},
                "output": [OUTPUT_URL],
            },
        )
    )
    poll_route = respx.get(POLL_URL).mock(
        return_value=httpx.Response(200, json={"status": "succeeded"})
    )
    respx.get(OUTPUT_URL).mock(return_value=httpx.Response(200, content=b"png"))

    out = generate_image("anything")
    assert out == b"png"
    assert not poll_route.called


@respx.mock
def test_generate_image_supports_string_output(monkeypatch):
    """Replicate sometimes returns ``output`` as a single URL string."""
    monkeypatch.setattr("shortstack_worker.sources.flux.time.sleep", lambda _s: None)

    respx.post(REPLICATE_PREDICT_URL).mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "abc",
                "status": "succeeded",
                "urls": {"get": POLL_URL},
                "output": OUTPUT_URL,
            },
        )
    )
    respx.get(OUTPUT_URL).mock(return_value=httpx.Response(200, content=b"png"))

    assert generate_image("x") == b"png"


@respx.mock
def test_generate_image_failure_raises(monkeypatch):
    monkeypatch.setattr("shortstack_worker.sources.flux.time.sleep", lambda _s: None)

    respx.post(REPLICATE_PREDICT_URL).mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "abc",
                "status": "starting",
                "urls": {"get": POLL_URL},
            },
        )
    )
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(
            200,
            json={"id": "abc", "status": "failed", "error": "model crashed"},
        )
    )

    with pytest.raises(FluxGenerationError) as exc_info:
        generate_image("x")
    assert "failed" in str(exc_info.value)


@respx.mock
def test_generate_image_canceled_raises(monkeypatch):
    monkeypatch.setattr("shortstack_worker.sources.flux.time.sleep", lambda _s: None)

    respx.post(REPLICATE_PREDICT_URL).mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "abc",
                "status": "canceled",
                "urls": {"get": POLL_URL},
            },
        )
    )
    with pytest.raises(FluxGenerationError):
        generate_image("x")


@respx.mock
def test_generate_image_times_out(monkeypatch):
    """A long-running prediction that never succeeds should time out cleanly."""
    monkeypatch.setattr("shortstack_worker.sources.flux.time.sleep", lambda _s: None)

    # Drive a fake monotonic clock past the deadline on the second poll.
    times = iter([0.0, 0.0, 0.5, 100.0, 200.0])
    monkeypatch.setattr(
        "shortstack_worker.sources.flux.time.monotonic",
        lambda: next(times),
    )

    respx.post(REPLICATE_PREDICT_URL).mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "abc",
                "status": "starting",
                "urls": {"get": POLL_URL},
            },
        )
    )
    respx.get(POLL_URL).mock(
        return_value=httpx.Response(
            200, json={"id": "abc", "status": "processing"}
        )
    )
    with pytest.raises(FluxGenerationError) as exc_info:
        generate_image("x", poll_interval_sec=0.0, poll_timeout_sec=1.0)
    assert "timed out" in str(exc_info.value)


@respx.mock
def test_generate_image_raises_http_error_on_create_5xx():
    respx.post(REPLICATE_PREDICT_URL).mock(
        return_value=httpx.Response(503, json={"detail": "down"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        generate_image("x")


@respx.mock
def test_generate_image_succeeded_but_empty_output(monkeypatch):
    monkeypatch.setattr("shortstack_worker.sources.flux.time.sleep", lambda _s: None)

    respx.post(REPLICATE_PREDICT_URL).mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "abc",
                "status": "succeeded",
                "urls": {"get": POLL_URL},
                "output": [],
            },
        )
    )
    with pytest.raises(FluxGenerationError):
        generate_image("x")
