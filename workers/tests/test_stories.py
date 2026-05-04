"""Phase 8 unit tests. Pure-helper tests (no DB).

The story-mode entry point reuses the same Sonnet + persist path as
``generate_script``; the DB-bound branches are deferred until we have a real
postgres test fixture (same policy as Phase 2). These tests cover:

  * ``_build_story_payload`` length validation + payload shape
  * Task name / registration for ``generate_script_from_story``
  * That story-mode validation surfaces as ``ValueError`` to callers
"""

from __future__ import annotations

import pytest

from shortstack_core.enums import ScriptMode
from shortstack_worker.tasks.scripts import (
    STORY_MAX_LEN,
    STORY_MIN_LEN,
    _build_story_payload,
    generate_script_from_story,
)


def test_build_story_payload_shape():
    text = "  This is a perfectly fine story for the ShortStack pipeline to consume.  "
    payload = _build_story_payload(text)
    assert payload["source"] == "story"
    assert payload["url"] is None
    # title is the stripped story, truncated to 80 chars
    assert payload["title"] == text.strip()[:80].strip()
    assert payload["summary"] == text.strip()


def test_build_story_payload_title_truncates_at_80():
    long_text = "A" * 200
    payload = _build_story_payload(long_text)
    assert len(payload["title"]) == 80
    assert payload["summary"] == long_text


def test_build_story_payload_rejects_too_short():
    with pytest.raises(ValueError, match="at least"):
        _build_story_payload("hi")
    # Whitespace doesn't count toward the minimum.
    with pytest.raises(ValueError, match="at least"):
        _build_story_payload("   short    ")


def test_build_story_payload_rejects_too_long():
    too_long = "x" * (STORY_MAX_LEN + 1)
    with pytest.raises(ValueError, match="at most"):
        _build_story_payload(too_long)


def test_build_story_payload_accepts_exact_bounds():
    at_min = "a" * STORY_MIN_LEN
    payload_min = _build_story_payload(at_min)
    assert payload_min["summary"] == at_min

    at_max = "b" * STORY_MAX_LEN
    payload_max = _build_story_payload(at_max)
    assert payload_max["summary"] == at_max


def test_build_story_payload_rejects_non_string():
    with pytest.raises(ValueError, match="must be a string"):
        _build_story_payload(None)  # type: ignore[arg-type]


def test_story_mode_enum_value():
    # Sanity: the helper threads ScriptMode.STORY into the persist path.
    assert ScriptMode.STORY.value == "story"


def test_generate_script_from_story_task_registered():
    assert (
        generate_script_from_story.name
        == "shortstack_worker.tasks.scripts.generate_from_story"
    )


def test_generate_script_from_story_validates_length_before_db():
    """Story-text length is validated before any DB / Sonnet call. A too-short
    story raises ``ValueError`` synchronously; nothing about niches matters
    yet."""
    with pytest.raises(ValueError, match="at least"):
        generate_script_from_story.run(
            "00000000-0000-0000-0000-000000000000", "tiny"
        )
    with pytest.raises(ValueError, match="at most"):
        generate_script_from_story.run(
            "00000000-0000-0000-0000-000000000000", "x" * (STORY_MAX_LEN + 1)
        )


# --- API-layer validation (QA fixer pass) ---


def test_story_in_strips_before_length_check():
    """QA fix: Pydantic ``StoryIn`` and the worker helper used to disagree on
    whitespace boundaries. Both now strip-then-check; the API rejects a
    whitespace-padded too-short string consistently with the worker.
    """
    from pydantic import ValidationError

    from shortstack_api.serializers import StoryIn

    # 8 real chars + 4 spaces = 12 raw chars. Pre-fix: Pydantic accepted (>=10),
    # worker rejected (<10 stripped). Post-fix: Pydantic rejects.
    with pytest.raises(ValidationError):
        StoryIn(niche_slug="ai-productivity", story_text="hi there  ")

    # A valid story with surrounding whitespace is normalized to the stripped
    # form so the worker doesn't see leading/trailing spaces.
    obj = StoryIn(
        niche_slug="ai-productivity",
        story_text="   This is a long enough story for ShortStack.   ",
    )
    assert obj.story_text.startswith("This")
    assert obj.story_text.endswith("ShortStack.")


def test_story_in_rejects_invalid_niche_slug():
    """Slug must match ``[a-z0-9-]+`` and be 1..64 chars."""
    from pydantic import ValidationError

    from shortstack_api.serializers import StoryIn

    valid_text = "x" * 50
    with pytest.raises(ValidationError):
        StoryIn(niche_slug="UPPERCASE", story_text=valid_text)
    with pytest.raises(ValidationError):
        StoryIn(niche_slug="bad slug with spaces", story_text=valid_text)
    with pytest.raises(ValidationError):
        StoryIn(niche_slug="x" * 100, story_text=valid_text)
    with pytest.raises(ValidationError):
        StoryIn(niche_slug="", story_text=valid_text)
    # Valid ones pass.
    StoryIn(niche_slug="ai-productivity", story_text=valid_text)
    StoryIn(niche_slug="no-code-tools-2", story_text=valid_text)
