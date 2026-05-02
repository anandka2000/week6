"""Phase 2: script generation with Sonnet 4.6.

  generate_script(trend_id) -> creates a Script row + Video(pending_assets|failed)
                               row. Reprompts up to MAX_REPROMPTS times on
                               Pydantic validation failure. Records one
                               cost_event per Sonnet call.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from celery import shared_task
from celery.utils.log import get_task_logger
from pydantic import ValidationError

from shortstack_core.cost import (
    estimate_video_cost_cents,
    record_llm,
)
from shortstack_core.db import Niche, Script, Trend, Video, session_scope
from shortstack_core.enums import ScriptMode, ScriptStatus, VideoStatus
from shortstack_core.llm import UsageInfo, call_messages, extract_json
from shortstack_core.prompts import load_prompt
from shortstack_core.schemas import NichePersona, ScriptDraft

from ..celery_app import app  # noqa: F401  (ensures app is registered)

log = get_task_logger(__name__)

PROMPT_VERSION = "scripts_v1"
SCRIPT_MODEL = "claude-sonnet-4-6"
MAX_REPROMPTS = 2  # initial attempt + 2 retries = 3 total Sonnet calls


def _user_message(persona: NichePersona, trend_payload: dict[str, Any]) -> str:
    return json.dumps(
        {
            "persona": persona.model_dump(),
            "trend": trend_payload,
            "instruction": "Write the script now.",
        },
        ensure_ascii=False,
    )


def _validate_payload(text: str) -> ScriptDraft:
    """Parse JSON from ``text`` and validate against ``ScriptDraft``.

    ``prompt_version`` and ``model`` are filled in if Sonnet omitted them.
    """
    payload = extract_json(text)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object, got {type(payload).__name__}")
    payload.setdefault("prompt_version", PROMPT_VERSION)
    payload.setdefault("model", SCRIPT_MODEL)
    return ScriptDraft.model_validate(payload)


@shared_task(
    name="shortstack_worker.tasks.scripts.generate",
    autoretry_for=(),  # No retry on the task; reprompt loop handles transient JSON issues.
    acks_late=True,
)
def generate_script(trend_id: str) -> dict[str, Any]:
    trend_uuid = UUID(trend_id)

    with session_scope() as s:
        trend = s.get(Trend, trend_uuid)
        if trend is None:
            raise ValueError(f"trend {trend_id} not found")
        niche = s.get(Niche, trend.niche_id)
        if niche is None:
            raise ValueError(f"niche {trend.niche_id} for trend {trend_id} not found")
        persona = NichePersona.model_validate(niche.persona_json)
        trend_payload = {
            "title": trend.title,
            "summary": trend.summary or "",
            "source": trend.source.value if hasattr(trend.source, "value") else str(trend.source),
            "url": trend.url,
        }
        niche_id = niche.id
        cost_cap = niche.cost_cap_cents

    system = load_prompt("scripts_v1.md")
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": _user_message(persona, trend_payload)}
    ]
    usages: list[UsageInfo] = []

    draft: ScriptDraft | None = None
    last_error: str | None = None

    for attempt in range(MAX_REPROMPTS + 1):
        resp = call_messages(
            model=SCRIPT_MODEL,
            system=system,
            messages=messages,
            max_tokens=2048,
            cache_system=True,
        )
        usages.append(resp.usage)
        log.info(
            "generate_script.attempt",
            extra={
                "trend_id": trend_id,
                "attempt": attempt,
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "cache_read": resp.usage.cache_read_tokens,
            },
        )
        try:
            draft = _validate_payload(resp.text)
            break
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            messages.append({"role": "assistant", "content": resp.text})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"VALIDATION_ERROR:\n{last_error}\n\n"
                        "Fix only the offending fields and re-emit the entire JSON object."
                    ),
                }
            )

    # If validation never succeeded we still want the cost events recorded
    # against the niche so the spend isn't invisible. There is no Video to
    # attribute them to in that case.
    if draft is None:
        with session_scope() as s:
            for i, u in enumerate(usages):
                record_llm(
                    s,
                    niche_id=niche_id,
                    model=u.model,
                    input_tokens=u.input_tokens,
                    output_tokens=u.output_tokens,
                    cache_read_tokens=u.cache_read_tokens,
                    cache_write_tokens=u.cache_write_tokens,
                    meta={
                        "task": "generate_script",
                        "attempt": i,
                        "prompt_version": PROMPT_VERSION,
                        "trend_id": trend_id,
                    },
                )
        raise ValueError(
            f"script validation failed after {MAX_REPROMPTS + 1} attempts: {last_error}"
        )

    estimate = estimate_video_cost_cents(draft)

    with session_scope() as s:
        script = Script(
            trend_id=trend_uuid,
            niche_id=niche_id,
            mode=ScriptMode.TREND,
            draft_json=draft.model_dump(),
            prompt_version=PROMPT_VERSION,
            status=ScriptStatus.VALIDATED,
        )
        s.add(script)
        s.flush()

        if estimate > cost_cap:
            video_status = VideoStatus.FAILED
            failure_reason = f"cost_cap_estimate ({float(estimate):.2f}c > {cost_cap}c)"
        else:
            video_status = VideoStatus.PENDING_ASSETS
            failure_reason = None

        video = Video(
            script_id=script.id,
            niche_id=niche_id,
            status=video_status,
            cost_estimate_cents=int(estimate),
            cost_cents=0,
            failure_reason=failure_reason,
        )
        s.add(video)
        s.flush()
        video_id = video.id

        # Record one cost_event per Sonnet call now that the Video row exists,
        # so script-gen spend rolls up into ``videos.cost_cents``. Same
        # transaction so the video is guaranteed visible to ``record_cost``.
        for i, u in enumerate(usages):
            record_llm(
                s,
                niche_id=niche_id,
                model=u.model,
                input_tokens=u.input_tokens,
                output_tokens=u.output_tokens,
                cache_read_tokens=u.cache_read_tokens,
                cache_write_tokens=u.cache_write_tokens,
                video_id=video_id,
                meta={
                    "task": "generate_script",
                    "attempt": i,
                    "prompt_version": PROMPT_VERSION,
                    "trend_id": trend_id,
                },
            )

        return {
            "script_id": str(script.id),
            "video_id": str(video_id),
            "estimate_cents": float(estimate),
            "cap_cents": cost_cap,
            "status": video_status.value,
            "failure_reason": failure_reason,
            "draft": draft.model_dump(),
            "attempts": len(usages),
        }
