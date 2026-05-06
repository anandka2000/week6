"""LLM wrapper tests."""

from __future__ import annotations

import json

import httpx
import respx

from shortstack_core.llm import call, extract_json


def _anthropic_response(text: str, *, input_tokens: int = 100, output_tokens: int = 50) -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-4-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    }


@respx.mock
def test_call_returns_text_and_usage(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    # Reset cached client/settings
    import shortstack_core.llm as llm
    import shortstack_core.settings as st

    st._settings = None
    llm._client = None

    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json=_anthropic_response("hello world"))
    )

    resp = call(
        model="claude-haiku-4-5",
        system="you are a test",
        user="say hello",
        max_tokens=64,
    )
    assert resp.text == "hello world"
    assert resp.usage.input_tokens == 100
    assert resp.usage.output_tokens == 50


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    raw = "Here you go:\n```json\n{\"a\": 1, \"b\": [2, 3]}\n```\n"
    assert extract_json(raw) == {"a": 1, "b": [2, 3]}


def test_extract_json_unfenced_with_prefix():
    """LLMs sometimes prepend prose ('Here you go:'). extract_json now
    recovers JSON embedded in prose by taking the substring from first
    `{` to last `}` (or `[`...`]`). Pure-JSON-only behavior was changed
    in the QA cycle — we'd rather salvage a sloppy response than crash
    the whole task."""
    assert extract_json('blah blah {"a": 1}') == {"a": 1}
    assert extract_json("Here you go: [1, 2, 3] thanks") == [1, 2, 3]


def test_extract_json_empty_raises_value_error():
    """extract_json now raises ValueError (not JSONDecodeError) with the
    raw text included so logs show what the model actually returned."""
    import pytest

    with pytest.raises(ValueError, match="empty"):
        extract_json("")
    with pytest.raises(ValueError, match="empty"):
        extract_json("   \n   ")


def test_extract_json_unparseable_raises_value_error_with_context():
    """Unparseable responses include a truncated copy of the raw text so
    operators can debug without instrumenting the call site."""
    import pytest

    with pytest.raises(ValueError, match="no parseable JSON"):
        extract_json("definitely not json at all")
