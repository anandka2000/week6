"""Replicate / Flux Schnell image generation.

Uses Replicate's "model predictions" endpoint (no version pinning required)
for ``black-forest-labs/flux-schnell``. Polls the prediction until it reaches
a terminal state, then downloads the first output URL.
"""

from __future__ import annotations

import time

import httpx

from shortstack_core.settings import get_settings

REPLICATE_PREDICT_URL = (
    "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions"
)

POLL_INTERVAL_SEC = 1.0
POLL_TIMEOUT_SEC = 30.0


class FluxGenerationError(RuntimeError):
    """Raised when Replicate returns ``failed`` / ``canceled`` or times out."""


def _auth_headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Token {settings.replicate_api_token}",
        "Content-Type": "application/json",
    }


def generate_image(
    prompt: str,
    *,
    aspect_ratio: str = "9:16",
    client: httpx.Client | None = None,
    poll_interval_sec: float = POLL_INTERVAL_SEC,
    poll_timeout_sec: float = POLL_TIMEOUT_SEC,
) -> bytes:
    """Generate one image and return its raw PNG bytes.

    Raises :class:`FluxGenerationError` on failure or timeout, and
    :class:`httpx.HTTPError` on transport errors (so the celery autoretry can
    catch them).
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        create_resp = client.post(
            REPLICATE_PREDICT_URL,
            json={
                "input": {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "num_outputs": 1,
                    "output_format": "png",
                }
            },
            headers=_auth_headers(),
        )
        create_resp.raise_for_status()
        prediction = create_resp.json()

        poll_url = (prediction.get("urls") or {}).get("get")
        status = prediction.get("status")
        if status in {"succeeded", "failed", "canceled"}:
            final = prediction
        elif not poll_url:
            raise FluxGenerationError(
                f"replicate response missing urls.get and status={status!r}"
            )
        else:
            final = _poll_until_terminal(
                client,
                poll_url,
                interval_sec=poll_interval_sec,
                timeout_sec=poll_timeout_sec,
            )

        if final.get("status") != "succeeded":
            raise FluxGenerationError(
                f"replicate prediction status={final.get('status')!r} "
                f"error={final.get('error')!r}"
            )

        output = final.get("output")
        if isinstance(output, list):
            if not output:
                raise FluxGenerationError("replicate succeeded but output list empty")
            output_url = output[0]
        elif isinstance(output, str):
            output_url = output
        else:
            raise FluxGenerationError(
                f"replicate succeeded but output has unexpected shape: {type(output).__name__}"
            )

        img_resp = client.get(output_url)
        img_resp.raise_for_status()
        return img_resp.content
    finally:
        if owns_client:
            client.close()


def _poll_until_terminal(
    client: httpx.Client,
    poll_url: str,
    *,
    interval_sec: float,
    timeout_sec: float,
) -> dict:
    """Poll ``poll_url`` until status is terminal. Returns the last payload."""
    deadline = time.monotonic() + timeout_sec
    while True:
        resp = client.get(poll_url, headers=_auth_headers())
        resp.raise_for_status()
        payload = resp.json()
        status = payload.get("status")
        if status in {"succeeded", "failed", "canceled"}:
            return payload
        if time.monotonic() >= deadline:
            raise FluxGenerationError(
                f"replicate prediction timed out after {timeout_sec}s (last status={status!r})"
            )
        time.sleep(interval_sec)
