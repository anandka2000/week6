# Open questions

## Phase 1 prerequisites (trends)
- [ ] Pick subreddit list for `ai-productivity` niche (start: r/productivity, r/getdisciplined, r/artificial, r/ChatGPT?)
- [ ] Confirm YouTube Data API quota allocation (default 10k units/day — enough?)
- [ ] Decide pytrends rate limit handling (proxy pool vs. backoff-only)

## Brand / channel setup
- [ ] Confirm "Trending Tech" channel naming convention for niche channels
- [ ] Pick ElevenLabs voice ID for first niche (`ai-productivity`)
- [ ] Channel art / thumbnail template — does the dashboard need to manage these?

## Cost
- [ ] Build pricing table in `packages/core/cost.py` (LLM, TTS, image, render) — needs current published rates
- [ ] Decide stock-relevance score threshold (default 6/10, may need tuning)
- [ ] Decide what "hero scene only gets Flux" means for scripts with strong scene 0 already covered by stock

## Render
- [ ] Caption style: word-by-word highlight color, font, max-3-line wrap policy
- [ ] CTA bar: persistent vs. last-3-seconds-only
- [ ] Transitions between scenes: hard cut vs. crossfade

## Publishing
- [ ] YouTube category ID for "AI productivity" content (probably 28 — Science & Tech)
- [ ] Default visibility on first publish: `unlisted` (DoD says yes for v0)

## Approval gate
- [ ] Auto-approve heuristic thresholds (caption coverage %, audio LUFS range, duration window)
- [ ] After how many consecutive flops do we re-enable manual review?

## Dashboard
- [ ] Auth — needed for v0? (DoD says no. Keep behind `localhost`.)
