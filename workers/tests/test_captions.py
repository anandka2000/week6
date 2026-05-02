"""Phase 3 unit tests for the captions task. Pure logic only -- the
faster-whisper module is replaced in ``sys.modules`` before importing the
task module so no real model is ever loaded.
"""

from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass


# Install a fake ``faster_whisper`` module *before* the task module is
# imported anywhere in this test process. The task imports ``faster_whisper``
# lazily inside ``get_whisper_model``, so this stub is only consulted if a
# test actually exercises model loading -- but installing it up-front keeps
# pytest collection safe even on machines without faster-whisper installed.
if "faster_whisper" not in sys.modules:
    fake = types.ModuleType("faster_whisper")

    class _FakeModel:  # pragma: no cover - never instantiated in unit tests
        def __init__(self, *a, **kw) -> None:
            raise RuntimeError("real WhisperModel must not be constructed in tests")

        def transcribe(self, *a, **kw):
            raise RuntimeError("real transcribe must not be called in tests")

    fake.WhisperModel = _FakeModel  # type: ignore[attr-defined]
    sys.modules["faster_whisper"] = fake


from shortstack_core.schemas import CaptionsDoc, Word  # noqa: E402

from shortstack_worker.tasks.captions import (  # noqa: E402
    _words_from_segments,
    transcribe_audio,
)


@dataclass
class _FakeWord:
    word: str
    start: float
    end: float


@dataclass
class _FakeSegment:
    words: list[_FakeWord] | None


def test_words_from_segments_flattens_segments():
    segs = (
        _FakeSegment(words=[
            _FakeWord(word="hello", start=0.0, end=0.4),
            _FakeWord(word="world", start=0.4, end=0.9),
        ]),
        _FakeSegment(words=[
            _FakeWord(word="again", start=1.0, end=1.5),
        ]),
    )
    words = _words_from_segments(segs)
    assert [w.text for w in words] == ["hello", "world", "again"]
    assert words[0].start == 0.0
    assert words[0].end == 0.4
    assert words[2].start == 1.0
    assert words[2].end == 1.5
    assert all(isinstance(w, Word) for w in words)


def test_words_from_segments_skips_segments_without_word_timing():
    segs = (
        _FakeSegment(words=None),
        _FakeSegment(words=[_FakeWord(word="ok", start=0.0, end=0.2)]),
        _FakeSegment(words=[]),
    )
    words = _words_from_segments(segs)
    assert len(words) == 1
    assert words[0].text == "ok"


def test_captions_doc_json_round_trip():
    segs = (
        _FakeSegment(words=[
            _FakeWord(word="round", start=0.0, end=0.3),
            _FakeWord(word="trip", start=0.3, end=0.7),
        ]),
    )
    doc = CaptionsDoc(words=_words_from_segments(segs))
    raw = doc.model_dump_json()
    parsed = json.loads(raw)
    assert parsed == {
        "words": [
            {"text": "round", "start": 0.0, "end": 0.3},
            {"text": "trip", "start": 0.3, "end": 0.7},
        ]
    }
    rebuilt = CaptionsDoc.model_validate_json(raw)
    assert rebuilt == doc


def test_transcribe_audio_is_registered_celery_task():
    assert transcribe_audio.name == "shortstack_worker.tasks.captions.transcribe_audio"
