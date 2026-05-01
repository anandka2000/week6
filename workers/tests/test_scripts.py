"""Phase 2 unit tests. Pure logic only (no DB). DB-integration tests need a
real Postgres and are tracked in TODO.md.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from shortstack_core.llm import call_messages
from shortstack_worker.tasks.scripts import (
    PROMPT_VERSION,
    SCRIPT_MODEL,
    _user_message,
    _validate_payload,
)


def _valid_payload() -> dict[str, Any]:
    return {
        "hook": "Three minutes of friction is killing your focus.",
        "scenes": [
            {
                "index": 0,
                "narration": "Three minutes of friction is killing your focus.",
                "on_screen_text": "FRICTION = TAX",
                "visual_prompt": "close-up of a cluttered desk with sticky notes",
                "duration_sec": 2.5,
            },
            {
                "index": 1,
                "narration": "Most productivity gurus tell you to add more tools to your stack.",
                "on_screen_text": "",
                "visual_prompt": "a desk with too many gadgets and apps open",
                "duration_sec": 4.0,
            },
            {
                "index": 2,
                "narration": "I disagree. The best move is subtraction.",
                "on_screen_text": "SUBTRACT, DON'T ADD",
                "visual_prompt": "minimalist desk with one notebook and a pen",
                "duration_sec": 4.0,
            },
            {
                "index": 3,
                "narration": "Pick one tool. Use it for a month. Delete the rest.",
                "on_screen_text": "ONE TOOL. ONE MONTH.",
                "visual_prompt": "hand pressing delete on a phone home screen",
                "duration_sec": 5.0,
            },
        ],
        "cta": "Hit follow if you're killing the bloat this month.",
        "total_duration_sec": 15.5,
    }


def _anthropic_response(text: str, *, in_tok: int = 800, out_tok: int = 200) -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": SCRIPT_MODEL,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    }


def test_validate_payload_happy():
    draft = _validate_payload(json.dumps(_valid_payload()))
    assert draft.scenes[0].index == 0
    assert draft.prompt_version == PROMPT_VERSION
    assert draft.model == SCRIPT_MODEL


def test_validate_payload_fenced_json():
    draft = _validate_payload("```json\n" + json.dumps(_valid_payload()) + "\n```")
    assert len(draft.scenes) == 4


def test_validate_payload_rejects_bad_hook():
    p = _valid_payload()
    p["hook"] = " ".join(["word"] * 20)
    with pytest.raises(Exception):
        _validate_payload(json.dumps(p))


def test_validate_payload_rejects_long_scene_zero():
    p = _valid_payload()
    p["scenes"][0]["duration_sec"] = 4.5
    p["total_duration_sec"] = 15.5 + 2.0
    with pytest.raises(Exception):
        _validate_payload(json.dumps(p))


def test_user_message_includes_persona_and_trend():
    from shortstack_core.schemas import NichePersona

    persona = NichePersona(
        brand="Trending Tech: AI Productivity",
        voice_id="vox-1",
        subreddits=["productivity"],
        banned_topics=["politics"],
    )
    msg = _user_message(persona, {"title": "X", "summary": "Y", "source": "reddit", "url": None})
    obj = json.loads(msg)
    assert obj["persona"]["brand"] == "Trending Tech: AI Productivity"
    assert obj["trend"]["title"] == "X"
    assert "instruction" in obj


@respx.mock
def test_call_messages_threads_history(monkeypatch):
    """call_messages sends the full message list each turn so reprompts can
    use the cached system block."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    import shortstack_core.llm as llm
    import shortstack_core.settings as st

    st._settings = None
    llm._client = None

    seen: list[dict] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=_anthropic_response("ok"))

    respx.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)

    history = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ]
    resp = call_messages(
        model=SCRIPT_MODEL, system="cached system", messages=history, max_tokens=128
    )
    assert resp.text == "ok"
    body = seen[0]
    assert body["messages"] == history
    # system arrives as a list with cache_control when cache_system=True (default)
    assert isinstance(body["system"], list)
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
