# Open questions & follow-ups

## All 9 kickoff phases — done. `make setup` one-shot installer also done.

Phase status table in `docs/USER_GUIDE.md` is the source of truth. Open
follow-ups below are non-blocking polish.

## Setup-time gotchas — all fixed in code

These came out of real-machine debugging on macOS + Ubuntu. Each has a
commit fix; listed here so future operators / sessions know they were
real and where the recovery lives. Full table in `docs/PROJECT_STATUS.md`
("Setup-time gotchas" section).

- Node 25 too new for Remotion → `setup.sh` installs Node 22 LTS (`fff5896` baseline)
- pnpm 11 needs Node 22.13+ → enforced in setup.sh
- `--env-file` flag rejected by older docker compose → dropped (`9e1eace`)
- Docker Compose v2 plugin missing on Colima/Podman → auto-detect both forms (`5e6e667`)
- Corepack `pnpm@latest` fetch fails → multi-step fallback ending in pnpm-9 binary (`437b331`)
- brew refuses to symlink over Corepack shim → `corepack disable` first (`1668c83`)
- npmjs.org `%2F` URLs blocked by corp WAF / captive portal → pnpm-9 binary has no runtime fetch (`437b331`)
- SSL cert verification failure (corp MITM) → operator action: install corp CA + set `NODE_EXTRA_CA_CERTS` etc. (in `DECISIONS.md`)
- alembic spawn from `infra/` subdir → run from repo root with `-c infra/alembic.ini` (`fff5896`)
- alembic `Path doesn't exist: migrations` from repo root → use `%(here)s` template (`5d78ac7`)
- `uv sync` skipped workspace members → root pyproject explicitly depends on all 4 (`8824013`)
- `/review` 422 from URL/dependency parameter mismatch → renamed `slug` → `niche` in dependency (`4ae875d`)
- `e2e_stub` saw ".env missing keys" even with `.env` populated → `get_settings()` reads `.env`; `os.environ` doesn't (`cae941f`)
- Haiku cluster output truncated by `max_tokens=2048` → bigger budget + tighter prompt + smaller batch (`33c38d5`)
- Cross-machine dashboard Approve → `TypeError: Failed to fetch` because `API_BASE` was hardcoded to `localhost:8000` in client bundle → new `clientApiBase()` derives from `window.location.hostname` at click-time; `ReviewActions.tsx` + `submitStory()` use it
- `make publish` with empty `VIDEO=` reported confusing typer error (`Got unexpected extra argument`) → Makefile `require` macro fails fast with `VIDEO is required — e.g. 'make publish VIDEO=<value>'` (applied to every required-arg target)

## Phase 9 — done
- [x] `should_auto_approve(...)` heuristic in `packages/core/shortstack_core/quality.py` (duration, caption coverage, cost ceiling, flop streak)
- [x] `render_video` calls the heuristic; pass → APPROVED, fail → PENDING_REVIEW with reasons in `failure_reason`
- [x] `daily_pipeline(niche_id, max_videos)` runs the full chain N times honoring `niches.daily_quota`
- [x] `publish_approved(niche_id, platform, visibility)` — picks up APPROVED videos with no Publication and queues publish
- [x] Beat: `daily_pipeline_all` 10:00 UTC + `publish_approved_all` 11:00 UTC (1h gap for human override via /review)
- [x] CLI: `automation daily --niche <slug> [--max N]`, `automation publish-approved --niche <slug>`
- [x] Make: `make produce NICHE=<slug> [MAX=N]`, `make publish-approved NICHE=<slug>`
- [x] 11 new tests in `test_quality.py` (every gate fires; flop-streak math) + 6 in `test_automation.py` (registration + beat schedule)

## Phase 9 leftovers (defer; nice-to-have)
- [ ] Real audio-loudness check via ffmpeg (currently we only proxy via caption coverage)
- [ ] Make the auto-approve hold-period configurable (default 1h between auto-approve and auto-publish, encoded as the gap between the two beat entries)
- [ ] Surface `failure_reason="auto_review: ..."` text on the dashboard /review page so the operator sees the heuristic's reasons inline
- [ ] Per-niche thresholds (overriding the env defaults) — useful if some niches need longer / shorter videos
- [ ] Behavioural test that `render_video` actually transitions to APPROVED vs PENDING_REVIEW based on `should_auto_approve` (the existing test only checks the import is wired)
- [ ] `pick_next` consumes the trend before the rest of the chain runs — if any later step fails, the trend is lost for the day. Either roll back `consumed_at` on chain-failure, or only consume after `render_video` succeeds.

## Phase 8 — done
- [x] `_generate(...)` extracted from `generate_script` as the shared Sonnet + persist helper (mode-aware, preserves trend-mode contract)
- [x] `generate_script_from_story(niche_id, story_text)` Celery task with 10–5000 char validation
- [x] `_build_story_payload(story_text)` pure helper for the trend-shaped payload (`source="story"`, title=first 80 chars)
- [x] `POST /videos/from-story` API endpoint (sync, `201 Created`, returns `{script_id, video_id, estimate_cents, status}`)
- [x] Dashboard `/stories` page + client `StoryForm` (char counter, niche dropdown, deep-link to /videos)
- [x] Tests: 9 new in `test_stories.py`; existing `test_scripts.py` (6) all pass after the refactor

## Phase 8 leftovers (defer; nice-to-have)
- [ ] Dashboard error UX: parse FastAPI `detail[].msg` instead of showing raw 422 body
- [ ] Decide whether `from_story` should kick off Celery `apply_async` for long stories rather than `.run` (currently sync; operator gets the video_id immediately)

## Phase 7 — done
- [x] `BufferPublisher` (Buffer Publishing API v2: upload-media → create-update; per-niche profile_id)
- [x] `NichePersona.buffer_profiles` JSONB field (Platform.value → profile_id)
- [x] `Settings.buffer_access_token` env var
- [x] `_publisher_for(platform, persona)` routes IG / TikTok / X / LinkedIn → Buffer; YouTube → existing publisher
- [x] `publish_video_all(video_id, platforms, visibility)` Celery task — sequential fan-out, per-platform error capture, never aborts on one failure
- [x] CLI: `publish all --video-id <uuid> --platforms ig_reels,tiktok,x,linkedin`
- [x] Tests: respx round-trip for BufferPublisher; multi-platform fan-out happy + partial failure

## Phase 7 leftovers (defer; nice-to-have)
- [ ] Buffer endpoint shape uncertainty — confirm the assumed `upload-media` and `updates/create.json` shapes against the live API on first real upload
- [ ] Per-platform retry policy on `publish_video_all` (currently one-shot; operator re-dispatches failed slugs)
- [ ] Slot scheduling per niche (Buffer rate limits + approval queue) — needs a `Slot` table + cron
- [ ] Decide whether Buffer-backed posts get `Platform.BUFFER` or stay as the native platform value (current: native — `Platform.IG_REELS`, etc.)

## Phase 6 leftovers (defer; nice-to-have)
- [ ] YouTube Analytics API for `avg_view_duration_sec`, `retention_curve`, `ctr` (Data API only exposes counts)
- [ ] Sonnet Batch API for the weekly learnings synthesis (50% off, 24h SLA — fine for weekly cadence)
- [ ] Surface learnings.md content on the dashboard so the operator can see what the model is feeding back

## Phase 6 — done
- [x] `snapshot_metrics(publication_id)` Celery task pulling YouTube Data API stats
- [x] Schedule t+24h / t+72h / t+7d ETAs at publish time
- [x] Beat-driven `nightly_catchup` (02:00 UTC) for missed publications
- [x] `weekly_learnings(niche_id)` Sonnet synthesis → `niches/{niche_id}/learnings_v1.md` in S3
- [x] Beat-driven `weekly_learnings_all` (Sun 02:00 UTC) fans out per niche
- [x] Script-gen `load_learnings(niche_id)` appends to system prompt on next run
- [x] `GET /metrics/by-video` API + dashboard `/metrics` page (views, likes, cost, margin proxy)
- [x] CLI: `analytics snapshot --publication-id` + `analytics learnings --niche`
- [x] Make: `make snapshot PUBLICATION=<uuid>`, `make learnings NICHE=<slug>`

## Phase 5 — done
- [x] `Publisher` ABC + `VideoMetadata` schema in `packages/publishers/shortstack_publishers/base.py`
- [x] `YouTubeShortsPublisher` (OAuth refresh-token → resumable upload via httpx)
- [x] Worker `publish_video(video_id, platform, visibility)` Celery task
- [x] Status transitions: `approved → publishing → published`; rollback to `approved` on `PublishError`
- [x] Idempotent on `(video_id, platform)`; sets `selfDeclaredMadeForKids=false` + `containsSyntheticMedia=true`
- [x] CLI: `publish video --video-id <uuid>`. Make: `make publish VIDEO=<uuid>`

## Phase 4 — done
- [x] `apps/render/src/compositions/Vertical.tsx` — Ken Burns, word-by-word captions, fade-in CTA bar
- [x] POST `/render`: bundle once + cache, `selectComposition` honoring `calculateMetadata`, S3 upload via `@aws-sdk/client-s3`
- [x] Worker `render_video(video_id)` → signs S3 URLs, POSTs the body, records cost, `pending_render → pending_review`
- [x] CLI: `render video --video-id <uuid>`. Make: `make render-video VIDEO=<uuid>`
- [x] e2e-stub chains real render when `RENDER_SERVICE_URL` is reachable; falls back to demo flip otherwise

## Phase 3 — done
- [x] `generate_scene_visual(video_id, script_id, scene_index)` Pexels-first / Flux-fallback (Haiku graded)
- [x] `synthesize_voiceover(video_id, script_id)` ElevenLabs Turbo
- [x] `transcribe_audio(video_id, audio_asset_id)` faster-whisper word-level
- [x] `generate_assets(video_id)` orchestrator + rolling cost cap (`check_video_cap` after every record_*)
- [x] All assets land under `videos/{video_id}/` in MinIO
- [x] CLI: `assets generate --video-id <uuid>`
- [x] e2e-stub adapts to which API keys are present

## Phase 3 leftovers (small, can do anytime)
- [ ] Asset reuse cache keyed by sha1(visual_prompt + style) per niche — would zero out repeat-image cost
- [ ] Surface soft-cap warning on the video row (currently structlog only) so the dashboard can flag it
- [ ] Pexels page_url is sent to Haiku as the candidate "src", but the grader probably should see image URLs not page URLs — verify with first real run

## Phase 2 — done
- [x] `scripts_v1.md` system prompt with hook framework + scene-0 hook constraint + CTA rewrite
- [x] `generate_script(trend_id)` Celery task with reprompt loop (max 2 retries)
- [x] Pre-asset cost estimate stamped on video row, hard-cap fail-fast
- [x] CLI: `scripts generate --trend-id <uuid>`
- [x] Tests for prompt builder, validation helper, multi-turn LLM dispatch

## Phase 1 follow-ups
- [ ] YouTube Data API v3 source (`workers/shortstack_worker/sources/youtube.py`) with category 28 filter
- [ ] Google Trends source via pytrends with backoff
- [ ] Migrate Reddit fetch from `/hot.json` to PRAW + OAuth before we hit unauth rate limits
- [ ] Tune Haiku cluster prompt with real outputs; confirm output structure stays stable

## Cost
- [ ] Verify all vendor prices in `packages/core/shortstack_core/cost.py` against current rate cards
- [ ] Decide stock-relevance score threshold (default 6/10) once Phase 3 is in
- [ ] Add weekly cost rollup to dashboard
- [ ] Promote `Video.cost_cents` from `Integer` to `Numeric` via a new alembic
      migration so the rolling per-video rollup keeps sub-cent precision (see
      DECISIONS.md 2026-05-02). Until then `record_cost` rounds to nearest cent
      on each event; reporting off `cost_events` is exact.

## Brand / channel
- [ ] Replace `REPLACE_WITH_ELEVENLABS_VOICE_ID` in seed with the real voice id for `ai-productivity`
- [ ] Confirm "Trending Tech: <Niche>" naming convention for niche channels
- [ ] Channel art / thumbnail template — does the dashboard need to manage these?

## Render (Phase 4)
- [ ] Caption style: word-by-word highlight color, font, max-3-line wrap policy
- [ ] CTA bar: persistent vs. last-3-seconds-only
- [ ] Transitions: hard cut vs. crossfade

## Publishing (Phase 5)
- [ ] YouTube category id (probably 28 - Science & Tech)
- [ ] Default visibility on first publish: `unlisted` (per DoD)
- [ ] YouTube `selfDeclaredMadeForKids=false` + synthetic-content disclosure flag baked into the upload payload

## Approval gate
- [ ] Auto-approve heuristic thresholds (caption coverage %, audio LUFS range, duration window) — Phase 9
- [ ] After how many consecutive flops do we re-enable manual review?

## Infra
- [ ] CI: pytest + ruff + tsc on PR. Probably GitHub Actions.
- [ ] Decide whether to swap MinIO for Cloudflare R2 in staging
- [ ] Backup strategy for postgres in prod
