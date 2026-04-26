"""End-to-end stub: trend → score → pick → stub script + video in pending_review.

Run ``make e2e-stub`` (passes NICHE=ai-productivity by default).

What this proves:
  * docker stack is up (postgres reachable)
  * migrations applied
  * niche seeded
  * trend fetcher works (Reddit hot.json)
  * either Haiku is wired up (clusters get scored) OR fallback scoring works
  * approval gate row is created and visible at /review

What this does NOT do (deferred to later phases):
  * generate a real script with Sonnet
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
from shortstack_core.schemas import Scene, ScriptDraft
from shortstack_worker.tasks import trends as trend_tasks

NICHE_SLUG = os.environ.get("NICHE", "ai-productivity")


def _placeholder_draft(title: str) -> ScriptDraft:
    """Stub script: 4 scenes of 4s each. Real Sonnet generation is Phase 2."""
    return ScriptDraft(
        hook=title[:90],
        scenes=[
            Scene(
                index=i,
                narration=f"placeholder narration line {i}",
                on_screen_text="",
                visual_prompt="placeholder visual",
                duration_sec=4.0,
            )
            for i in range(4)
        ],
        cta="Follow for more.",
        total_duration_sec=16.0,
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

    print(f"[1/4] fetch_reddit niche={NICHE_SLUG}")
    fetched = trend_tasks.fetch_reddit.run(niche_id)
    print(f"      wrote {fetched['written']} new trend rows")

    if os.environ.get("ANTHROPIC_API_KEY"):
        print("[2/4] cluster (Haiku)")
        trend_tasks.cluster.run(niche_id)
    else:
        print("[2/4] ANTHROPIC_API_KEY missing — fallback: hook_score=5 on unscored trends")
        with session_scope() as s:
            s.execute(
                update(Trend)
                .where(Trend.niche_id == uuid.UUID(niche_id))
                .where(Trend.hook_score.is_(None))
                .where(Trend.consumed_at.is_(None))
                .values(hook_score=5)
            )

    print("[3/4] pick_next")
    picked = trend_tasks.pick_next.run(niche_id)
    if picked is None:
        print(
            "      no eligible trend in last 48h. did fetch find anything?",
            file=sys.stderr,
        )
        return 3
    print(f"      picked: '{picked['title']}' (score={picked['hook_score']})")

    print("[4/4] create stub script + pending_review video")
    with session_scope() as s:
        draft = _placeholder_draft(picked["title"])
        script = Script(
            trend_id=uuid.UUID(picked["trend_id"]),
            niche_id=uuid.UUID(niche_id),
            mode=ScriptMode.TREND,
            draft_json=draft.model_dump(),
            prompt_version="stub_v0",
            status=ScriptStatus.DRAFT,
        )
        s.add(script)
        s.flush()
        video = Video(
            script_id=script.id,
            niche_id=uuid.UUID(niche_id),
            status=VideoStatus.PENDING_REVIEW,
            cost_estimate_cents=0,
            cost_cents=0,
        )
        s.add(video)
        s.flush()
        print(f"      video_id={video.id}")
        print(f"      review at: http://localhost:3000/review")
    return 0


if __name__ == "__main__":
    sys.exit(main())
