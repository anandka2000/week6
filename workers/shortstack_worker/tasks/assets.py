"""Phase 3 orchestrator: visuals → tts → captions, then flip pending_render.

  generate_assets(video_id) calls the per-asset tasks inline (``.run(...)``)
  in dependency order. Each sub-task is itself idempotent so this whole task
  can be retried after a partial failure and pick up where it left off.

  Cost cap is enforced inside the per-asset tasks (each ``record_*`` is
  followed by ``check_video_cap``). When ``CostCapExceeded`` propagates here
  we set the video to FAILED with a ``cost_cap`` failure_reason and re-raise.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from celery import shared_task
from celery.utils.log import get_task_logger

from shortstack_core.cost import CostCapExceeded
from shortstack_core.db import Script, Video, session_scope
from shortstack_core.enums import VideoStatus
from shortstack_core.schemas import ScriptDraft

from .captions import transcribe_audio
from .tts import synthesize_voiceover
from .visuals import generate_scene_visual

log = get_task_logger(__name__)


@shared_task(
    name="shortstack_worker.tasks.assets.generate_assets",
    acks_late=True,
)
def generate_assets(video_id: str) -> dict[str, Any]:
    video_uuid = UUID(video_id)

    # Load + status check + reset on retry
    with session_scope() as s:
        video = s.get(Video, video_uuid)
        if video is None:
            raise ValueError(f"video {video_id} not found")
        if video.status not in {VideoStatus.PENDING_ASSETS, VideoStatus.FAILED}:
            log.info(
                "generate_assets.skip",
                extra={"video_id": video_id, "status": video.status.value},
            )
            return {
                "video_id": video_id,
                "status": video.status.value,
                "skipped": True,
            }
        script = s.get(Script, video.script_id)
        if script is None:
            raise ValueError(f"script {video.script_id} for video {video_id} not found")
        draft = ScriptDraft.model_validate(script.draft_json)
        script_id_str = str(script.id)
        n_scenes = len(draft.scenes)
        if video.status == VideoStatus.FAILED:
            video.status = VideoStatus.PENDING_ASSETS
            video.failure_reason = None

    visuals_results: list[dict[str, Any]] = []

    try:
        for i in range(n_scenes):
            log.info("generate_assets.visual", extra={"scene": i, "of": n_scenes})
            visuals_results.append(
                generate_scene_visual.run(video_id, script_id_str, i)
            )

        log.info("generate_assets.tts")
        tts_result = synthesize_voiceover.run(video_id, script_id_str)

        log.info("generate_assets.captions")
        captions_result = transcribe_audio.run(video_id, tts_result["asset_id"])

    except CostCapExceeded as e:
        with session_scope() as s:
            v = s.get(Video, video_uuid)
            if v is not None:
                v.status = VideoStatus.FAILED
                v.failure_reason = (
                    f"cost_cap ({float(e.cost_cents):.2f}c > {e.cap_cents}c)"
                )
        raise

    with session_scope() as s:
        v = s.get(Video, video_uuid)
        if v is not None and v.status == VideoStatus.PENDING_ASSETS:
            v.status = VideoStatus.PENDING_RENDER

    return {
        "video_id": video_id,
        "n_scenes": n_scenes,
        "visuals": visuals_results,
        "voice": tts_result,
        "captions": captions_result,
        "next_status": VideoStatus.PENDING_RENDER.value,
    }
