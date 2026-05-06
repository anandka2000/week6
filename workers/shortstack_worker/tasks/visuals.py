"""Phase 3 visuals slice: generate one scene image (Pexels first, Flux fallback).

  generate_scene_visual(video_id, script_id, scene_index) -> dict
    1. Loads the validated ScriptDraft + Niche.
    2. Picks the scene by index.
    3. Hero scene (index 0): straight to Flux.
       Other scenes: Pexels search -> Haiku relevance grader. If best_index is
       null or score < 6, fall through to Flux.
    4. Records a cost_event for the LLM grader and the image. Enforces the
       per-video hard cap after each charge.
    5. Uploads the image to S3 and inserts an Asset row.

Idempotent: if an ``image`` asset with the matching ``scene_index`` already
exists for the script we short-circuit and return its info rather than
calling Pexels / Replicate again.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import httpx
from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select

from shortstack_core.cost import (
    CostCapExceeded,
    check_video_cap,
    record_image,
    record_llm,
)
from shortstack_core.db import Asset, Niche, Script, session_scope
from shortstack_core.enums import AssetKind
from shortstack_core.llm import call as llm_call
from shortstack_core.llm import extract_json
from shortstack_core.prompts import load_prompt
from shortstack_core.schemas import Scene, ScriptDraft
from shortstack_core.storage import upload_bytes, video_key

from ..celery_app import app  # noqa: F401  (ensures app is registered)
from ..sources import flux, pexels

log = get_task_logger(__name__)

RELEVANCE_PROMPT = "visual_relevance_v1.md"
RELEVANCE_MODEL = "claude-haiku-4-5"
RELEVANCE_THRESHOLD = 6
HERO_SCENE_INDEX = 0


def _is_hero_scene(scene_index: int) -> bool:
    """Hero (scene 0) bypasses Pexels and goes straight to Flux."""
    return scene_index == HERO_SCENE_INDEX


def _build_relevance_user_message(
    visual_prompt: str, candidates: list[pexels.PexelsPhoto]
) -> str:
    return json.dumps(
        {
            "visual_prompt": visual_prompt,
            "candidates": [
                {"index": i, "alt": p.alt, "src": p.page_url}
                for i, p in enumerate(candidates)
            ],
        },
        ensure_ascii=False,
    )


def _parse_relevance_response(text: str) -> tuple[int | None, int, str]:
    """Parse the Haiku grader's JSON output into (best_index, score, rationale).

    Tolerates fenced or unfenced JSON. Returns ``best_index=None`` when the
    grader signals a fallback (either explicitly or via score < threshold).
    Raises ``ValueError`` when the payload is unusable.
    """
    payload = extract_json(text)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object, got {type(payload).__name__}")

    raw_best = payload.get("best_index")
    raw_score = payload.get("score")
    rationale = payload.get("rationale", "") or ""

    if raw_score is None:
        raise ValueError("missing 'score' field in relevance response")
    try:
        score = int(raw_score)
    except (TypeError, ValueError) as e:
        raise ValueError(f"score is not an int: {raw_score!r}") from e

    best_index: int | None
    if raw_best is None:
        best_index = None
    else:
        try:
            best_index = int(raw_best)
        except (TypeError, ValueError) as e:
            raise ValueError(f"best_index is not an int or null: {raw_best!r}") from e

    # Caller-side enforcement of the threshold even if the model forgot.
    if best_index is not None and score < RELEVANCE_THRESHOLD:
        best_index = None

    return best_index, score, str(rationale)


def _select_provider_for_scene(
    scene: Scene,
    *,
    scene_index: int,
    pexels_search,
    relevance_grader,
    flux_available: bool = True,
) -> tuple[str, list[pexels.PexelsPhoto], int | None, int | None, str]:
    """Pure decision helper. Returns (provider, candidates, chosen_index, score, rationale).

    Used by the celery task; broken out so unit tests can exercise the
    Pexels-vs-Flux branching without standing up a database.

    ``pexels_search`` and ``relevance_grader`` are dependency-injected
    callables so tests don't need to monkey-patch globals.
    ``relevance_grader`` is invoked as ``(visual_prompt, candidates) -> (best_index, score, rationale)``.

    If ``flux_available`` is False (no Replicate token), every Flux fallback
    becomes a Pexels fallback instead. Hero scene takes the first Pexels
    hit unconditionally; non-hero scenes that would have fallen back to
    Flux take the highest-ranked Pexels candidate (or first one if the
    grader said best_index is None). This keeps the pipeline running on
    Pexels-only setups; quality on the hero scene takes a small hit but
    nothing crashes.
    """
    if _is_hero_scene(scene_index):
        if flux_available:
            return ("flux-schnell", [], None, None, "hero scene")
        # Pexels-only mode: search for the hero too, take the first hit.
        candidates = pexels_search(scene.visual_prompt)
        if candidates:
            return ("pexels", candidates, 0, None, "hero (pexels-only mode)")
        # No Pexels results either: nothing we can do.
        return ("none", [], None, None, "no pexels hits and no flux configured")

    candidates = pexels_search(scene.visual_prompt)
    if not candidates:
        if flux_available:
            return ("flux-schnell", [], None, None, "no pexels hits")
        return ("none", [], None, None, "no pexels hits and no flux configured")

    best_index, score, rationale = relevance_grader(scene.visual_prompt, candidates)
    if best_index is None:
        if flux_available:
            return ("flux-schnell", candidates, None, score, rationale)
        # Pexels-only: take the first candidate even though grader didn't like any.
        return ("pexels", candidates, 0, score, f"{rationale} (pexels-only fallback)")
    if best_index < 0 or best_index >= len(candidates):
        # Defensive: model hallucinated an out-of-range index; fall back.
        if flux_available:
            return ("flux-schnell", candidates, None, score, "best_index out of range")
        return ("pexels", candidates, 0, score, "best_index out of range (pexels-only)")

    return ("pexels", candidates, best_index, score, rationale)


def _ext_for_provider(provider: str) -> tuple[str, str]:
    """Map provider -> (file extension, content type)."""
    if provider == "pexels":
        return ("jpg", "image/jpeg")
    if provider == "flux-schnell":
        return ("png", "image/png")
    raise ValueError(f"unknown image provider {provider!r}")


@shared_task(
    name="shortstack_worker.tasks.visuals.generate_scene_visual",
    acks_late=True,
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def generate_scene_visual(
    video_id: str, script_id: str, scene_index: int
) -> dict[str, Any]:
    script_uuid = UUID(script_id)
    video_uuid = UUID(video_id)

    # 1) Idempotency check + load draft / niche inside a session.
    with session_scope() as s:
        existing = s.scalar(
            select(Asset).where(
                Asset.script_id == script_uuid,
                Asset.kind == AssetKind.IMAGE,
                Asset.scene_index == scene_index,
            )
        )
        if existing is not None:
            log.info(
                "generate_scene_visual.idempotent_hit",
                extra={
                    "script_id": script_id,
                    "scene_index": scene_index,
                    "asset_id": str(existing.id),
                },
            )
            return {
                "asset_id": str(existing.id),
                "provider": existing.provider,
                "s3_key": existing.s3_key,
                "score": existing.meta.get("score"),
                "scene_index": scene_index,
            }

        script = s.get(Script, script_uuid)
        if script is None:
            raise ValueError(f"script {script_id} not found")
        niche = s.get(Niche, script.niche_id)
        if niche is None:
            raise ValueError(
                f"niche {script.niche_id} for script {script_id} not found"
            )

        draft = ScriptDraft.model_validate(script.draft_json)
        niche_id = niche.id
        cost_cap = niche.cost_cap_cents

    if scene_index < 0 or scene_index >= len(draft.scenes):
        raise ValueError(
            f"scene_index {scene_index} out of range for script {script_id} "
            f"(has {len(draft.scenes)} scenes)"
        )
    scene = draft.scenes[scene_index]

    # 2) Pick provider (Pexels with Haiku grader, or straight to Flux).
    def _grader(
        visual_prompt: str, candidates: list[pexels.PexelsPhoto]
    ) -> tuple[int | None, int, str]:
        user = _build_relevance_user_message(visual_prompt, candidates)
        resp = llm_call(
            model=RELEVANCE_MODEL,
            system=load_prompt(RELEVANCE_PROMPT),
            user=user,
            cache_system=True,
        )
        # Record the LLM cost regardless of how it influenced the choice.
        with session_scope() as s:
            record_llm(
                s,
                niche_id=niche_id,
                model=resp.usage.model,
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
                cache_read_tokens=resp.usage.cache_read_tokens,
                cache_write_tokens=resp.usage.cache_write_tokens,
                video_id=video_uuid,
                meta={
                    "task": "generate_scene_visual",
                    "scene_index": scene_index,
                    "prompt_version": "visual_relevance_v1",
                },
            )
            check_video_cap(s, video_id=video_uuid, hard_cap_cents=cost_cap)
        return _parse_relevance_response(resp.text)

    provider, candidates, chosen_index, score, rationale = _select_provider_for_scene(
        scene,
        scene_index=scene_index,
        pexels_search=lambda q: pexels.search_photos(q, per_page=5),
        relevance_grader=_grader,
        flux_available=bool(get_settings().replicate_api_token),
    )
    if provider == "none":
        raise ValueError(
            f"scene {scene_index}: no Pexels hits for {scene.visual_prompt!r} "
            "and REPLICATE_API_TOKEN isn't set, so Flux fallback isn't available either. "
            "Either set REPLICATE_API_TOKEN in .env or rephrase the visual_prompt."
        )

    # 3) Fetch image bytes from the chosen provider.
    fallback_used = provider == "flux-schnell" and not _is_hero_scene(scene_index)

    if provider == "pexels":
        assert chosen_index is not None
        chosen = candidates[chosen_index]
        image_bytes = pexels.download_photo(chosen.src_portrait)
    elif provider == "flux-schnell":
        image_bytes = flux.generate_image(scene.visual_prompt)
    else:  # pragma: no cover - guarded above
        raise ValueError(f"unsupported provider {provider!r}")

    # 4) Record image cost + enforce hard cap before persisting the asset.
    with session_scope() as s:
        record_image(
            s,
            niche_id=niche_id,
            provider=provider,
            n=1,
            video_id=video_uuid,
            meta={
                "task": "generate_scene_visual",
                "scene_index": scene_index,
                "fallback_used": fallback_used,
            },
        )
        check_video_cap(s, video_id=video_uuid, hard_cap_cents=cost_cap)

    # 5) Upload bytes to S3.
    ext, content_type = _ext_for_provider(provider)
    s3_key = upload_bytes(
        video_key(video_id, f"scene_{scene_index}.{ext}"),
        image_bytes,
        content_type=content_type,
    )

    # 6) Insert the Asset row.
    with session_scope() as s:
        asset = Asset(
            script_id=script_uuid,
            kind=AssetKind.IMAGE,
            scene_index=scene_index,
            provider=provider,
            s3_key=s3_key,
            meta={
                "score": score,
                "fallback_used": fallback_used,
                "rationale": rationale,
            },
        )
        s.add(asset)
        s.flush()
        asset_id = str(asset.id)

    log.info(
        "generate_scene_visual.done",
        extra={
            "script_id": script_id,
            "video_id": video_id,
            "scene_index": scene_index,
            "provider": provider,
            "asset_id": asset_id,
            "score": score,
            "s3_key": s3_key,
        },
    )

    return {
        "asset_id": asset_id,
        "provider": provider,
        "s3_key": s3_key,
        "score": score,
        "scene_index": scene_index,
    }


# Keep `CostCapExceeded` accessible at module level so callers in the
# orchestrator can `except` on it without re-importing from cost.
__all__ = [
    "CostCapExceeded",
    "_build_relevance_user_message",
    "_ext_for_provider",
    "_is_hero_scene",
    "_parse_relevance_response",
    "_select_provider_for_scene",
    "generate_scene_visual",
]
