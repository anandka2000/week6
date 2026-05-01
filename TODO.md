# Open questions & follow-ups

## Phase 3 (assets) — start here next
- [ ] Per-scene image generation: Pexels first (relevance graded by Haiku), Flux schnell fallback / hero scene
- [ ] ElevenLabs Turbo v2.5 TTS with the niche's pinned voice_id
- [ ] faster-whisper for word-level captions; persist as `CaptionsDoc` JSONB asset
- [ ] All assets land under `videos/{video_id}/` in MinIO
- [ ] On any cost_event, abort and mark video failed if rolling cost_cents > niche.cost_cap_cents (hard cap)
- [ ] Soft-cap warning on the video row (75¢ default) — log + flag, still continue
- [ ] Asset reuse cache keyed by sha1(visual_prompt + style) per niche

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
