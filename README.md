# ShortStack

AI short-video pipeline for **Trending Tech**.

```
trends  →  cluster + score  →  pick  →  script  →  assets  →  render  →  publish  →  metrics
 (1)         (1)               (1)      (2)        (3)       (4)       (5)        (6)
```

> **Read [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) first.** It's the canonical operator + developer guide — quick start, every setting, every CLI command, troubleshooting, the lot. This README is just the absolute basics + the phase status board.

## Quickstart

**Brand-new machine?** One command — installs Docker / uv / Node 22 / pnpm, boots the stack, migrates, seeds, runs tests:

```bash
make setup
```

Tested on macOS + Ubuntu 22/24 + Debian 12. Idempotent.

**Already set up?** Manual sequence:

```bash
cp .env.example .env       # add ANTHROPIC_API_KEY for real clustering
make up                    # postgres :5432, redis :6379, minio :9000/:9001
make install               # uv sync + pnpm install
make migrate               # apply alembic 0001_initial
make seed                  # adds the ai-productivity niche
make dev                   # api :8000, dashboard :3000, render :8787
```

In another terminal:

```bash
make worker                # start Celery (all 6 queues)
make beat                  # start Celery beat
```

## Try the pipeline

```bash
make trends-fetch    NICHE=ai-productivity   # Reddit hot.json -> trends table
make trends-cluster  NICHE=ai-productivity   # Haiku scores 1-10  (needs ANTHROPIC_API_KEY)
make trends-pick     NICHE=ai-productivity   # consume the highest-scored trend
make assets          VIDEO=<uuid>            # visuals + tts + captions for a video
make e2e-stub        NICHE=ai-productivity   # all of the above end-to-end
```

`make e2e-stub` adapts to whichever keys are available:

| keys present | pipeline runs through |
|---|---|
| (none) | trends → fallback score=5 → placeholder script → pending_review |
| `ANTHROPIC_API_KEY` | + Sonnet script generation, real cost estimate |
| + ElevenLabs + Pexels + Replicate + real `voice_id` | + visuals + tts + captions, status reaches pending_render |

Then visit http://localhost:3000/review and click **Approve**.

## Layout

```
apps/
  api/                  FastAPI: /health, /niches, /trends, /videos, /publications,
                                  /costs/daily, /videos/{id}/{approve,reject}
  dashboard/            Next.js 14: /, /niches, /trends, /videos, /review, /costs
  render/               Remotion (Hello composition) + Express :8787 (POST /render is 501 until Phase 4)
packages/
  core/                 schemas, enums, settings, db (SQLAlchemy 2.0), cost helpers,
                        Anthropic client wrapper (cached system prompts), structlog
  publishers/           empty stub (Phase 5+)
workers/
  shortstack_worker/    Celery app (6 queues), tasks/{health,trends}, sources/reddit,
                        cli/ (typer)
infra/
  docker-compose.yml    postgres + redis + minio (with auto-create bucket init)
  alembic.ini, migrations/
scripts/
  seed_niches.py        one-shot
  e2e_stub.py           wired up by `make e2e-stub`
```

## Cost guardrails

Every paid call records a `cost_event`. Per-video rollup lives on `videos.cost_cents`. A pre-asset `cost_estimate_cents` projection lets us fail fast above the hard cap. See `DECISIONS.md` for the optimization stack (stock-first imagery, Haiku for everything pre-script, prompt caching, ElevenLabs Turbo, asset reuse).

| Cap | Cents | Behavior |
|---|---|---|
| Soft warn | 75 | log + flag, still publish |
| Hard kill | 100 | abort with `failure_reason='cost_cap'` |

## Tests

```bash
uv run pytest                                  # all
uv run pytest packages/core/tests              # schema validation
uv run pytest workers/tests                    # cost math + reddit + llm wrapper
```

Tests use respx to mock Reddit + Anthropic; no API keys or network needed.

## Phase status

| Day / Phase | Status | Notes |
|---|---|---|
| Day 1: Skeleton | done | services boot |
| Day 2: Schemas + DB | done | 8 tables, alembic 0001 |
| Day 3: Celery + cost | done | 6 queues, pricing, structlog |
| Day 4: Trends (Reddit) | done | YouTube + GTrends sources still TODO |
| Day 5: Dashboard | done | read-only |
| Day 6: Approval gate | done | `make e2e-stub` |
| Day 7: Polish | done |  |
| **Phase 2: Script gen** | done | Sonnet 4.6, reprompt loop, scene-0 hook constraint, CTA rewrite |
| **Phase 3: Assets** | done | Pexels-first / Flux-fallback (Haiku grader), ElevenLabs Turbo, faster-whisper word timings, rolling cost cap |
| **Phase 4: Render** | done | Remotion 1080×1920 with Ken Burns, word-level captions, fade-in CTA. POST /render uploads mp4 to S3 |
| **Phase 5: Publisher** | done | YouTube Shorts via OAuth refresh-token + resumable upload; idempotent `(video_id, platform)` |
| **Phase 6: Analytics + feedback** | done | Snapshots at t+24/72h/7d, weekly Sonnet `learnings.md` feeds back into script-gen |
| **Phase 7: Multi-platform** | done | `BufferPublisher` + `publish_video_all` fan-out for IG/TikTok/X/LinkedIn |
| **Phase 8: User-story mode** | done | `POST /videos/from-story` skips trends; dashboard `/stories` form |
| **Phase 9: Full automation** | done | `should_auto_approve` heuristic in `render_video`; `daily_pipeline_all` (10 UTC) + `publish_approved_all` (11 UTC) beat |

All 9 kickoff phases shipped. See `TODO.md` for the polish backlog (live Buffer-shape verification, ffmpeg LUFS, dashboard surfacing of held-for-review reasons, per-niche threshold overrides).

## Per-asset pipeline (Phase 3)

```
generate_assets(video_id)
  ├─ for each scene i:
  │     generate_scene_visual(video_id, script_id, i)
  │       hero (i=0) → Flux schnell
  │       else → Pexels search → Haiku relevance grader
  │              score ≥ 6 → Pexels; else → Flux fallback
  ├─ synthesize_voiceover(video_id, script_id)
  │     ElevenLabs Turbo v2.5, persona.voice_id, mp3
  └─ transcribe_audio(video_id, audio_asset_id)
        faster-whisper base.en, word-level timestamps → captions.json

Each cost-incurring step calls check_video_cap; CostCapExceeded → Video.status = failed.
```

## Useful URLs (local)

- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:3000
- Review queue: http://localhost:3000/review
- MinIO console: http://localhost:9001 (login `shortstack` / `shortstack-dev-secret`)
