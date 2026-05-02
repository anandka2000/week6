# Open questions & follow-ups

## Phase 4 (Remotion render service) — start here next
- [ ] `apps/render/src/compositions/Vertical.tsx` taking `{ scenes, audioUrl, captions }` props
- [ ] Ken Burns on each image; word-level highlighted captions; bottom-third CTA bar
- [ ] POST `/render` in `apps/render/src/server.ts`: takes a `video_id`, downloads inputs from S3 via signed URLs, renders, writes `output.mp4` back to S3, returns the key
- [ ] Worker task `render_video(video_id)` calls the render service synchronously with a long timeout, then flips `pending_render -> pending_review`
- [ ] Update e2e-stub to chain through render when a `RENDER_SERVICE_URL` is reachable

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
