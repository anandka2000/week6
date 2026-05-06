"""End-to-end stub: trend → score → pick → script (Sonnet, when key is set; placeholder otherwise) → review.

Run ``make e2e-stub`` (passes NICHE=ai-productivity by default).

What this proves:
  * docker stack is up (postgres reachable)
  * migrations applied
  * niche seeded
  * trend fetcher works (Reddit hot.json)
  * either Haiku is wired up (clusters get scored) OR fallback scoring works
  * if ANTHROPIC_API_KEY is set: real Sonnet script generation, cost estimate stamped
  * approval gate row is created and visible at /review

What this does NOT do (deferred to Phase 3+):
  * generate assets, audio, captions
  * render an actual mp4
  * publish to YouTube
"""

from __future__ import annotations

import os
import sys
import uuid

from sqlalchemy import select, update

from shortstack_core.db import Niche, Script, Trend, Video, session_scope
from shortstack_core.enums import ScriptMode, ScriptStatus, VideoStatus
from shortstack_core.schemas import VOICE_ID_PLACEHOLDER, NichePersona, Scene, ScriptDraft
from shortstack_core.settings import get_settings
from shortstack_worker.tasks import assets as asset_tasks
from shortstack_worker.tasks import render as render_tasks
from shortstack_worker.tasks import scripts as script_tasks
from shortstack_worker.tasks import trends as trend_tasks

NICHE_SLUG = os.environ.get("NICHE", "ai-productivity")


def _placeholder_draft(title: str) -> ScriptDraft:
    """Stub script when ANTHROPIC_API_KEY is missing. Real Sonnet path is preferred."""
    hook = " ".join(title.split()[:12]) or "placeholder hook"
    scenes = [
        Scene(
            index=0,
            narration="placeholder hook line",
            on_screen_text="",
            visual_prompt="placeholder visual",
            duration_sec=2.5,
        )
    ]
    scenes.extend(
        Scene(
            index=i,
            narration=f"placeholder narration line {i}",
            on_screen_text="",
            visual_prompt="placeholder visual",
            duration_sec=4.0,
        )
        for i in range(1, 4)
    )
    return ScriptDraft(
        hook=hook,
        scenes=scenes,
        cta="Follow for more.",
        total_duration_sec=14.5,
        prompt_version="stub_v0",
        model="stub",
    )


def main() -> int:
    with session_scope() as s:
        niche = s.execute(
            select(Niche).where(Niche.slug == NICHE_SLUG)
        ).scalar_one_or_none()
        if niche is None:
            print(
                f"niche {NICHE_SLUG!r} not seeded. Run `make seed`.",
                file=sys.stderr,
            )
            return 2
        niche_id = str(niche.id)

    print(f"[1/5] fetch_reddit niche={NICHE_SLUG}")
    fetched = trend_tasks.fetch_reddit.run(niche_id)
    print(f"      wrote {fetched['written']} new trend rows")

    # Settings is the single source of truth for keys — pydantic-settings
    # reads .env so editing the file alone is enough; no need to `export`
    # or `set -a` before `make e2e-stub`. ``os.environ`` only sees keys
    # that the calling shell explicitly exported.
    settings = get_settings()
    have_anthropic = bool(settings.anthropic_api_key)
    if have_anthropic:
        print("[2/5] cluster (Haiku)")
        trend_tasks.cluster.run(niche_id)
    else:
        print("[2/5] ANTHROPIC_API_KEY missing — fallback: hook_score=5 on unscored trends")
        with session_scope() as s:
            s.execute(
                update(Trend)
                .where(Trend.niche_id == uuid.UUID(niche_id))
                .where(Trend.hook_score.is_(None))
                .where(Trend.consumed_at.is_(None))
                .values(hook_score=5)
            )

    print("[3/5] pick_next")
    picked = trend_tasks.pick_next.run(niche_id)
    if picked is None:
        print(
            "      no eligible trend in last 48h. did fetch find anything?",
            file=sys.stderr,
        )
        return 3
    print(f"      picked: '{picked['title']}' (score={picked['hook_score']})")

    if have_anthropic:
        print("[4/5] generate_script (Sonnet)")
        result = script_tasks.generate_script.run(picked["trend_id"])
        video_id = uuid.UUID(result["video_id"])
        print(
            f"      script_id={result['script_id']} video_id={video_id} "
            f"est={result['estimate_cents']:.2f}c status={result['status']} "
            f"attempts={result['attempts']}"
        )
    else:
        print("[4/5] no ANTHROPIC_API_KEY — writing placeholder Script + Video")
        with session_scope() as s:
            draft = _placeholder_draft(picked["title"])
            script = Script(
                trend_id=uuid.UUID(picked["trend_id"]),
                niche_id=uuid.UUID(niche_id),
                mode=ScriptMode.TREND,
                draft_json=draft.model_dump(),
                prompt_version="stub_v0",
                # Match real ``generate_script`` so 'validated' is the single
                # consistent shipping state regardless of which path created
                # the row.
                status=ScriptStatus.VALIDATED,
            )
            s.add(script)
            s.flush()
            video = Video(
                script_id=script.id,
                niche_id=uuid.UUID(niche_id),
                status=VideoStatus.PENDING_ASSETS,
                cost_estimate_cents=0,
                cost_cents=0,
            )
            s.add(video)
            s.flush()
            video_id = video.id
            print(f"      video_id={video_id}")

    # Phase 3 assets requires several API keys + a real voice_id; skip if any missing.
    have_assets_keys = bool(
        settings.elevenlabs_api_key
        and settings.pexels_api_key
        and settings.replicate_api_token
    )
    voice_id_set = False
    with session_scope() as s:
        niche_row = s.get(Niche, uuid.UUID(niche_id))
        if niche_row is not None:
            persona = NichePersona.model_validate(niche_row.persona_json)
            voice_id_set = persona.voice_id != VOICE_ID_PLACEHOLDER

    if have_anthropic and have_assets_keys and voice_id_set:
        print("[5/7] generate_assets (visuals -> tts -> captions)")
        try:
            assets_result = asset_tasks.generate_assets.run(str(video_id))
            print(
                f"      visuals={len(assets_result['visuals'])} "
                f"voice.chars={assets_result['voice']['characters']} "
                f"captions.words={assets_result['captions']['n_words']}"
            )
        except Exception as exc:  # noqa: BLE001 — demo path, surface and keep going
            print(f"      asset pipeline failed: {exc}")

        # Phase 4: real Remotion render. Falls back to demo flip if the render
        # service is unreachable so the demo still ends at /review.
        with session_scope() as s:
            v = s.get(Video, video_id)
            ready_to_render = v is not None and v.status == VideoStatus.PENDING_RENDER

        if ready_to_render:
            print("[6/7] render_video (Remotion)")
            try:
                render_result = render_tasks.render_video.run(str(video_id))
                print(
                    f"      mp4={render_result['s3_key_mp4']} "
                    f"took={render_result['render_ms']}ms "
                    f"cost={render_result['render_cost_cents']:.3f}c"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"      render failed: {exc} — falling back to demo flip")
                with session_scope() as s:
                    v = s.get(Video, video_id)
                    if v is not None and v.status == VideoStatus.PENDING_RENDER:
                        v.status = VideoStatus.PENDING_REVIEW
            print("[7/7] approval gate ready")
        else:
            with session_scope() as s:
                v = s.get(Video, video_id)
                status = v.status.value if v else "missing"
            print(f"[6/7] video status={status} — skipping render")
    else:
        # Build a per-key missing list so the operator sees exactly which one
        # to fix. Lumping the three asset keys together hid which was empty.
        missing = []
        if not have_anthropic:
            missing.append("ANTHROPIC_API_KEY")
        if not settings.elevenlabs_api_key:
            missing.append("ELEVENLABS_API_KEY")
        if not settings.pexels_api_key:
            missing.append("PEXELS_API_KEY")
        if not settings.replicate_api_token:
            missing.append("REPLICATE_API_TOKEN")
        if not voice_id_set:
            missing.append(
                "niche.persona_json.voice_id (still the placeholder — UPDATE it via psql)"
            )
        print(
            f"[5/5] skipping assets — missing: {', '.join(missing)} "
            "(see docs/USER_GUIDE.md or PROJECT_STATUS.md). Demo flip to pending_review."
        )
        with session_scope() as s:
            v = s.get(Video, video_id)
            if v is not None and v.status == VideoStatus.PENDING_ASSETS:
                v.status = VideoStatus.PENDING_REVIEW

    print("      review at: http://localhost:3000/review")
    return 0


if __name__ == "__main__":
    sys.exit(main())
