# DECISIONS

Architectural choices we've locked in. Add to this file with date + short rationale whenever a non-obvious tradeoff comes up.

## 2026-04-26 — Initial decisions

### Brand
Brand is **Trending Tech**. New YouTube channel created per niche (e.g. "Trending Tech: AI Productivity"). Every upload sets YouTube's `selfDeclaredMadeForKids=false` and the synthetic-content disclosure flag, plus an "AI-assisted" video tag.

### Voice
One persistent ElevenLabs `voice_id` per niche, stored on `niches.persona_json.voice_id`. Voice rotation = explicit niche fork, never a runtime knob. Default model: `eleven_turbo_v2_5` (~3× cheaper than Multilingual v2, fine for English shorts).

### Cost caps
- **Soft warn:** $0.75/video — log + flag, still publish.
- **Hard kill:** $1.00/video — job aborts with `failure_reason='cost_cap'`.
- Pre-asset `cost_estimate_cents` runs before any paid generation; fail fast if estimate > hard cap.

### Trends
- Recency window: **48h**. Older trends are not eligible for the picker.
- Dedup horizon: **30 days** within a niche (suppress topic if cluster covered ≤30 days ago).

### Render service
Same-box deployment. Worker calls `http://localhost:8787/render`. No separate render box until we hit a CPU wall.

### Cost optimizations baked in from day 1
1. Stock-first asset strategy: Pexels first, Flux schnell only when stock relevance <6/10 or for hero scene (scene 0).
2. ElevenLabs Turbo v2.5, not Multilingual v2.
3. Prompt caching on script-gen system prompt (persona + hook framework + learnings.md).
4. Haiku 4.5 for clustering, dedup, hook scoring, stock-relevance grading. Sonnet only writes the script.
5. Asset reuse cache keyed by `sha1(visual_prompt + style)` per niche.
6. Default scene count = 5 (hook + 3 + cta), median scene 4s.
7. Batch API for weekly learnings digest (Phase 6).

### Stack picks
- Backend: Python 3.11 + FastAPI + Pydantic v2 + SQLAlchemy 2 + Postgres 15 + Redis.
- Worker: Celery, one queue per phase.
- Render: Remotion (Node 20) behind Express, called via HTTP.
- Frontend: Next.js 14 App Router + Tailwind + shadcn/ui (read-only at first).
- Storage: MinIO locally; swap to Cloudflare R2 later (S3-compatible).
- Multi-platform v1: Buffer/Publer API behind a `Publisher` interface.
- Observability: structlog + OTel-to-stdout. Per-video cost logging is non-negotiable.

## 2026-04-26 — Implementation choices made during week 1

### Enums stored as VARCHAR + CHECK
SQLAlchemy `Enum(..., native_enum=False)` produces a column-level CHECK
constraint instead of a Postgres native ENUM type. Trade-off: zero-downtime
ALTERs on enum value sets are easier this way; the cost is slightly looser
type info in the DB. Acceptable for v0.

### Reddit via public hot.json (no OAuth) for v0
We hit `https://www.reddit.com/r/<sub>/hot.json` directly with httpx and a
polite User-Agent. Trade-off: lower rate limit and no access to subscribed
listings; but zero auth overhead and trivially testable with respx. PRAW
migration is in TODO.md.

### CLI uses typer, runs tasks inline (no Celery hop)
The operator CLI calls `task.run(...)` directly rather than `task.delay(...)`
so you can drive the trend pipeline without a worker. Real production pulls
go through beat + workers; the CLI is for ad-hoc.

### Approval gate uses simple status transitions
`pending_review -> approved` (publish-eligible) and `pending_review -> failed`
(rejected, with `failure_reason='rejected_in_review'`). No FSM library;
guarded by a single `_transition` helper in the videos router.

### Same-box render server is a stub for now
`apps/render` exposes `/health` and a 501 `/render`. Full implementation
is Phase 4; the server boots in `make dev` so the wiring is correct.

## 2026-05-01 — Phase 2 (script generation)

### Scene 0 is the hook (≤ 3.0s, ≤ 10 words)
The `ScriptDraft` validator now enforces both that `scenes[0].duration_sec` is
≤ 3.0 and that `scenes[0].narration` is ≤ 10 spoken words. This forces the
hook to actually fit in the first 3 seconds of playback, which is where the
algorithm decides whether to keep showing the video. Trade-off: more
reprompt loops on the first batch of scripts; that's fine because it
narrows what Sonnet can produce.

### CTA is rewritten per video, not copied verbatim
The cached system prompt instructs Sonnet to rewrite `persona.cta_template`
to be specific to the current video (≤ 12 words, same intent). Trade-off:
slightly more variability across videos; expected ~10% engagement uplift
based on prior data. We keep `cta_template` on the persona as the seed.

### Reprompt sends the validation error back as a user follow-up
Failed validation -> append assistant's bad output + a user message
prefixed `VALIDATION_ERROR:` -> call again. The system block is identical,
so the prompt cache stays warm and we mostly pay for the delta. Capped at
2 retries (3 calls total) before raising.

### Pre-asset cost estimate runs after generation, not before
We don't try to project cost without the script (you can't estimate TTS
char count without scenes). Generation itself is cheap (~1¢ per call) so
it's cheap to overshoot and reject. The estimate is stamped on
`videos.cost_estimate_cents`; when it exceeds `niche.cost_cap_cents`
the video row is created as `status='failed'` with
`failure_reason='cost_cap_estimate (...)'` rather than ever entering
`pending_assets`.

## 2026-05-02 — Phase 3 (assets)

### Asset orchestration is serial within one Celery task
`generate_assets(video_id)` calls `generate_scene_visual` per scene, then
`synthesize_voiceover`, then `transcribe_audio` — all via `.run(...)`
(inline, no queue hop). Sub-tasks are individually idempotent (skip on
existing Asset of the matching kind), so this whole task is safe to
retry; it picks up at the first missing asset.

We considered Celery `chord`/`group` for per-scene parallelism but the
serial pattern is simpler, the rolling cost-cap check is cleaner, and
typical scene counts are 4–6 so wall-clock cost is small. Revisit if
visuals dominate end-to-end latency.

### Rolling cost cap fires inside each producer
Every `record_*` is followed by `check_video_cap(session, video_id, ...)`
in the same transaction. `CostCapExceeded` propagates out of the task,
the orchestrator catches it, marks the video FAILED with
`failure_reason='cost_cap (...)'`, and re-raises. Already-paid-for assets
are kept (we already paid; the next retry can use them).

### Pexels candidates sent to Haiku include the page URL, not the image URL
The Haiku relevance grader sees `{index, alt, src=page_url}`. We're
sending the page URL as a stable, human-readable identifier, not because
Haiku can fetch images (it can't). This is a minor smell and may need to
become "alt-only" once we get real outputs. Tracked in TODO.md.

### Image extension is provider-driven
Pexels portrait CDN serves JPEG → `.jpg` / `image/jpeg`. Flux schnell
returns PNG → `.png` / `image/png`. The provider determines the suffix
on the s3 key; the render service doesn't need to know which.

### Whisper model is `base.en`, CPU, int8
Loaded lazily via `lru_cache`. Cheap enough to run on the worker box
and ~150MB model footprint. We can swap to `small.en` if accuracy
matters, or to GPU if throughput becomes a problem. No need yet.

## 2026-05-02 — Test-cycle fixes

### `estimate_llm_cost_cents` no longer subtracts `cache_read_tokens` from `input_tokens`
The Anthropic SDK already returns `usage.input_tokens` *excluding* cached
tokens (those are split into `cache_read_input_tokens` /
`cache_creation_input_tokens`). Subtracting `cache_read_tokens` again
double-discounted cache hits and produced negative costs whenever the
cache hit was larger than the live input. The helper now bills
`input_tokens` at the input rate and `cache_read_tokens` at the
cache-read rate independently. The test
`test_llm_cache_read_is_cheaper` was updated to encode the new semantics
(cached run is exactly `cache_read_per_mtok / input_per_mtok` of the
full price — for Sonnet that's exactly 10× cheaper).

### Pytest collection: switched to `--import-mode=importlib`
We have two test packages both named `tests/` (one under
`packages/core/`, one under `workers/`). Pytest's default `prepend`
import mode can't reconcile two same-named packages. We added
`addopts = "--import-mode=importlib"` to the existing
`[tool.pytest.ini_options]` block in `pyproject.toml` rather than
deleting the `__init__.py` files, because `importlib` mode is the
modern recommendation, doesn't mutate `sys.path`, and lets us add more
workspace-member test packages later without further collision.

### `record_cost` rounds (not truncates) when stamping `videos.cost_cents`
`Video.cost_cents` is a SQL `Integer`, but `record_cost` accumulates a
`Decimal` (sub-cent precision). Truncating toward zero with `int(...)`
under-counted the rolling cap by up to N cents per video — every cost
event under 1¢ effectively recorded as zero. We now `round` instead.
The proper fix is to promote the column to `Numeric`; that's a schema
migration and is tracked in `TODO.md`.
