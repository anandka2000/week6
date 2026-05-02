"""Pure-logic tests for the visuals task.

The celery task itself touches Postgres + S3 + Pexels + Replicate + Anthropic
and is exercised via the orchestrator integration test. Here we cover the
pure helpers that decide which provider runs and how the Haiku grader's
JSON response is parsed.
"""

# DB-integration test deferred -- requires a real Postgres + MinIO + live HTTP.

from __future__ import annotations

import json

import pytest

from shortstack_core.schemas import Scene
from shortstack_worker.sources.pexels import PexelsPhoto
from shortstack_worker.tasks.visuals import (
    HERO_SCENE_INDEX,
    RELEVANCE_THRESHOLD,
    _build_relevance_user_message,
    _ext_for_provider,
    _is_hero_scene,
    _parse_relevance_response,
    _select_provider_for_scene,
    generate_scene_visual,
)


def _scene(visual_prompt: str = "a hand on a phone") -> Scene:
    return Scene(
        index=1,
        narration="placeholder narration",
        on_screen_text="",
        visual_prompt=visual_prompt,
        duration_sec=4.0,
    )


def _photo(i: int = 0, alt: str = "alt") -> PexelsPhoto:
    return PexelsPhoto(
        id=1000 + i,
        page_url=f"https://example.com/p/{i}",
        src_portrait=f"https://example.com/p/{i}.jpg",
        alt=alt,
    )


# -- _is_hero_scene -----------------------------------------------------------


def test_is_hero_scene_only_index_zero():
    assert _is_hero_scene(0) is True
    assert _is_hero_scene(HERO_SCENE_INDEX) is True
    assert _is_hero_scene(1) is False
    assert _is_hero_scene(5) is False


# -- _parse_relevance_response ------------------------------------------------


def test_parse_relevance_response_happy():
    text = json.dumps({"best_index": 2, "score": 8, "rationale": "nice match"})
    best, score, rationale = _parse_relevance_response(text)
    assert best == 2
    assert score == 8
    assert rationale == "nice match"


def test_parse_relevance_response_handles_fenced_json():
    text = "```json\n" + json.dumps({"best_index": 0, "score": 9, "rationale": "x"}) + "\n```"
    best, score, _ = _parse_relevance_response(text)
    assert best == 0
    assert score == 9


def test_parse_relevance_response_explicit_null_best():
    text = json.dumps({"best_index": None, "score": 4, "rationale": "too generic"})
    best, score, rationale = _parse_relevance_response(text)
    assert best is None
    assert score == 4
    assert rationale == "too generic"


def test_parse_relevance_response_below_threshold_clears_best_index():
    """Even if the model returns a non-null index with score<threshold, we
    treat it as a fallback signal."""
    text = json.dumps(
        {"best_index": 1, "score": RELEVANCE_THRESHOLD - 1, "rationale": "meh"}
    )
    best, score, _ = _parse_relevance_response(text)
    assert best is None
    assert score == RELEVANCE_THRESHOLD - 1


def test_parse_relevance_response_at_threshold_keeps_best_index():
    text = json.dumps(
        {"best_index": 3, "score": RELEVANCE_THRESHOLD, "rationale": "borderline"}
    )
    best, score, _ = _parse_relevance_response(text)
    assert best == 3
    assert score == RELEVANCE_THRESHOLD


def test_parse_relevance_response_missing_rationale_is_empty_string():
    text = json.dumps({"best_index": 0, "score": 7})
    best, score, rationale = _parse_relevance_response(text)
    assert best == 0
    assert score == 7
    assert rationale == ""


def test_parse_relevance_response_missing_score_raises():
    text = json.dumps({"best_index": 0, "rationale": "no score"})
    with pytest.raises(ValueError):
        _parse_relevance_response(text)


def test_parse_relevance_response_non_int_score_raises():
    text = json.dumps({"best_index": 0, "score": "eight", "rationale": "x"})
    with pytest.raises(ValueError):
        _parse_relevance_response(text)


def test_parse_relevance_response_non_int_best_raises():
    text = json.dumps({"best_index": "two", "score": 8, "rationale": "x"})
    with pytest.raises(ValueError):
        _parse_relevance_response(text)


def test_parse_relevance_response_non_object_raises():
    with pytest.raises(ValueError):
        _parse_relevance_response("[1, 2, 3]")


# -- _build_relevance_user_message --------------------------------------------


def test_build_relevance_user_message_shape():
    photos = [_photo(0, alt="hand on phone"), _photo(1, alt="messy desk")]
    payload = json.loads(_build_relevance_user_message("delete app", photos))
    assert payload["visual_prompt"] == "delete app"
    assert payload["candidates"] == [
        {"index": 0, "alt": "hand on phone", "src": "https://example.com/p/0"},
        {"index": 1, "alt": "messy desk", "src": "https://example.com/p/1"},
    ]


def test_build_relevance_user_message_empty_candidates():
    payload = json.loads(_build_relevance_user_message("vp", []))
    assert payload == {"visual_prompt": "vp", "candidates": []}


# -- _ext_for_provider --------------------------------------------------------


def test_ext_for_provider_pexels_is_jpg():
    assert _ext_for_provider("pexels") == ("jpg", "image/jpeg")


def test_ext_for_provider_flux_is_png():
    assert _ext_for_provider("flux-schnell") == ("png", "image/png")


def test_ext_for_provider_unknown_raises():
    with pytest.raises(ValueError):
        _ext_for_provider("midjourney")


# -- _select_provider_for_scene ----------------------------------------------


def test_select_provider_hero_scene_skips_pexels():
    """Scene 0 must go straight to Flux without invoking Pexels or grader."""
    pexels_calls: list[str] = []
    grader_calls: list[str] = []

    def _pexels(q: str):
        pexels_calls.append(q)
        return [_photo(0)]

    def _grader(vp, cands):
        grader_calls.append(vp)
        return (0, 10, "would have used")

    provider, candidates, chosen, score, _ = _select_provider_for_scene(
        _scene(),
        scene_index=0,
        pexels_search=_pexels,
        relevance_grader=_grader,
    )
    assert provider == "flux-schnell"
    assert candidates == []
    assert chosen is None
    assert score is None
    assert pexels_calls == []
    assert grader_calls == []


def test_select_provider_no_pexels_hits_falls_back_to_flux():
    grader_calls = []

    def _pexels(q: str):
        return []

    def _grader(vp, cands):
        grader_calls.append(vp)
        return (0, 10, "x")

    provider, candidates, chosen, score, _ = _select_provider_for_scene(
        _scene(),
        scene_index=2,
        pexels_search=_pexels,
        relevance_grader=_grader,
    )
    assert provider == "flux-schnell"
    assert candidates == []
    assert chosen is None
    assert score is None
    # The grader must NOT be called when there are no candidates.
    assert grader_calls == []


def test_select_provider_grader_picks_a_pexels_photo():
    candidates_in = [_photo(0), _photo(1), _photo(2)]

    def _pexels(q: str):
        return candidates_in

    def _grader(vp, cands):
        return (1, 8, "good")

    provider, candidates, chosen, score, rationale = _select_provider_for_scene(
        _scene(),
        scene_index=3,
        pexels_search=_pexels,
        relevance_grader=_grader,
    )
    assert provider == "pexels"
    assert candidates is candidates_in
    assert chosen == 1
    assert score == 8
    assert rationale == "good"


def test_select_provider_grader_returns_null_falls_back_to_flux():
    """A grader response with best_index=None means 'use Flux'."""

    def _pexels(q: str):
        return [_photo(0), _photo(1)]

    def _grader(vp, cands):
        return (None, 4, "all generic")

    provider, _, chosen, score, rationale = _select_provider_for_scene(
        _scene(),
        scene_index=2,
        pexels_search=_pexels,
        relevance_grader=_grader,
    )
    assert provider == "flux-schnell"
    assert chosen is None
    assert score == 4
    assert rationale == "all generic"


def test_select_provider_out_of_range_index_falls_back_to_flux():
    def _pexels(q: str):
        return [_photo(0), _photo(1)]

    def _grader(vp, cands):
        # Hallucinated index past the candidate list.
        return (5, 9, "lying")

    provider, _, chosen, _, _ = _select_provider_for_scene(
        _scene(),
        scene_index=2,
        pexels_search=_pexels,
        relevance_grader=_grader,
    )
    assert provider == "flux-schnell"
    assert chosen is None


def test_select_provider_negative_index_falls_back_to_flux():
    def _pexels(q: str):
        return [_photo(0)]

    def _grader(vp, cands):
        return (-1, 9, "negative")

    provider, _, chosen, _, _ = _select_provider_for_scene(
        _scene(),
        scene_index=2,
        pexels_search=_pexels,
        relevance_grader=_grader,
    )
    assert provider == "flux-schnell"
    assert chosen is None


# -- celery registration ------------------------------------------------------


def test_generate_scene_visual_is_registered_celery_task():
    assert (
        generate_scene_visual.name
        == "shortstack_worker.tasks.visuals.generate_scene_visual"
    )
