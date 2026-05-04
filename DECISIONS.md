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

## 2026-05-02 — Phase 9 (full automation)

### Auto-approve gate lives in `render_video`, not in a separate task
After a successful render, the worker computes the auto-approve decision
inline before flipping status. Reasons: (a) the render task already has
the captions + cost + duration in scope, no extra DB hit; (b) one place
to change the rule of "what gets human review"; (c) if the gate fires,
the next-step pipeline (publish) just doesn't see the video — no
special handling needed.

### Heuristic checks (in order of how often they'll fire)
1. **Duration in `[15s, 60s]`** — outside this band YouTube Shorts deprioritises.
2. **Caption coverage `≥ 1.0` words/sec** — proxy for "the audio actually has narration the captions sync to."
3. **Cost under sanity ceiling (200¢)** — defence-in-depth on rolling cost-cap rounding bugs.
4. **Niche not on flop streak** — last N (default 3) published videos all under threshold (default 100 views).

Audio loudness (LUFS) is in the kickoff brief but skipped in v0; would
need ffmpeg analysis. Caption coverage is a serviceable proxy until we
have a real loudness check. Tracked in TODO.

### Held-for-review reason stuffed into `videos.failure_reason`
The column is named for failure but the data type and dashboard
treatment fit the auto-review-reasons use case. We prefix with
`"auto_review: "` so the dashboard can distinguish "real failure"
from "held for review" if it wants. Skipping a schema migration for v0.

### `daily_pipeline` runs sequentially per niche, niches in parallel
Beat-fired `daily_pipeline_all` enqueues one `daily_pipeline` task per
niche. Each niche's chain is sequential (`fetch → cluster → for each
quota slot: pick → script → assets → render`) but different niches run
on different workers. Trade-off: simpler bookkeeping at the cost of
not parallelising scenes within a video. The bottleneck is render
(10–60s) so per-niche parallelism is plenty.

### Pre-loop trends failures fail-soft, per-slot failures fail-soft
If `cluster()` raises (e.g. Anthropic outage, missing API key), the
whole `daily_pipeline` returns a `skipped="trends_unavailable"` summary
instead of crashing — symmetric with the per-slot `try/except` that
already kept other slots running when one video failed. Without this
catch the QA9 finding would manifest as silently-broken nightly cron
on any day Anthropic has a hiccup.

### `publish_approved_all` runs 1h *after* `daily_pipeline_all`
10:00 UTC → produce videos. 11:00 UTC → publish anything that survived
the auto-approve gate. The 1h gap is the operator's window to flip
auto-approved-but-actually-bad videos to FAILED via the dashboard
`/review` page. **Note:** the gap is per-niche-start, not per-video — a
niche whose pipeline finishes at 10:55 leaves the operator only ~5
minutes. Tunable via beat config; tracked as a leftover.

### Automation tasks route to the analytics queue
We didn't add a dedicated automation queue — the orchestrators are
low-priority cron work and the analytics queue already runs at a
cadence that suits them. Trade-off: noisy neighbours (a slow
`weekly_learnings` could delay `daily_pipeline_all`); we'll split the
queue if that ever bites.

### `AutoApproveDecision` is a frozen dataclass
Operator code that receives one cannot accidentally mutate the reasons
list. Pure-function semantics; trivially testable; matches the
"transient values, no hidden state" convention we've used for cost
and quality calculations elsewhere.

### Settings cross-validation: `min_duration ≤ max_duration`
A `model_validator(mode="after")` rejects a Settings instance where
the auto-approve duration window is inverted. Without this, swapping
`AUTO_APPROVE_MIN_DURATION_SEC` and `AUTO_APPROVE_MAX_DURATION_SEC`
in `.env` would silently hold every render at pending_review with no
obvious cause.

## 2026-05-02 — Phase 8 (user-story mode)

### `_generate(...)` is the shared persist path; `generate_script` is a thin wrapper
The previous `generate_script(trend_id)` body did three things: load the
trend, call Sonnet (with reprompt loop), persist Script + Video. We
extracted (2) + (3) into a private `_generate(*, niche_id, trend_payload,
mode, input_text=None, trend_id=None)` and `generate_script` became a
thin wrapper that does (1) and delegates. Story mode uses the same
helper with `mode=ScriptMode.STORY`. Trade-off: small refactor of an
existing-tested codepath; verified against the existing 6 test cases
which all still pass.

### `_build_story_payload` enforces 10–5000 chars at the helper boundary
Pydantic's `Field(min_length=10, max_length=5000)` on `StoryIn` catches
bad input at the API boundary and returns 422. The pure helper repeats
the check so direct callers (CLI, tests, future task callers) get the
same `ValueError` regardless of entry path. Trade-off: validation is in
two places; preferred over silent truncation or boundary-only checks.

### `POST /videos/from-story` is sync, not enqueued
We call `generate_script_from_story.run(...)` synchronously so the API
can return the resulting `{script_id, video_id, estimate_cents}` to the
operator immediately and the dashboard can deep-link to `/videos`. A
typical script-gen call is 3–8 seconds (Sonnet + reprompt budget) which
is acceptable for an interactive operator flow. If we ever take stories
from end users (not operators), switch to `apply_async` and return a
task_id.

### `Script.mode` and `Script.input_text` are first-class
Both columns existed in the schema since Day 2 but nothing wrote to
them. Story mode now writes `mode=STORY` + `input_text=story_text` so
analytics and learnings can later filter by entry mode if we see
mode-specific performance patterns.

### Dashboard form is a Client Component; the page is a Server Component
`apps/dashboard/app/stories/page.tsx` is a server component that fetches
niches and passes them as props to `<StoryForm>` (client). The form
owns the submit lifecycle (`useState` + `useTransition`) and shows the
result inline. Standard Next.js 14 App Router pattern; matches what
`/review` already does.

## 2026-05-02 — Phase 7 (multi-platform via Buffer)

### Buffer over Publer
Both have a Publishing API. Buffer is more widely used, has clearer docs,
and matches the kickoff brief verbatim. Publer is interchangeable — the
`Publisher` ABC means we can swap it in by writing `PublerPublisher` and
flipping `_publisher_for`. No schema change needed.

### One Buffer publisher per Platform, instantiated per call
`BufferPublisher(platform=..., profile_id=...)` is constructed inside
`_publisher_for(platform, persona)` — not a singleton. Reason: profile_id
is per-niche-per-platform (`persona.buffer_profiles[platform.value]`), and
the access token is per-account. Constructor cost is negligible (just
holds an httpx client).

### Buffer-backed posts get the *native* `Platform` value, not `Platform.BUFFER`
A post published via Buffer to Instagram Reels has `Publication.platform =
Platform.IG_REELS`, not a hypothetical `Platform.BUFFER`. Trade-off:
analytics queries by platform are correct without a join through Buffer;
downside is we can't tell at the row level whether the post went via
Buffer or natively. Acceptable for v0 — we can always add a
`Publication.via` column later.

### `publish_video_all` collects per-platform errors but never auto-retries
Sequential fan-out with `try/except` per platform. One platform failing
does not abort the others. Failed slugs are returned in the `errors`
array; the operator re-dispatches via
`shortstack-worker publish all --platforms <failed-slugs>`. Auto-retry
with backoff is a follow-up — until then we want the operator to see the
specific platform that failed and decide.

### `_run_single_publish` is a test seam
Inside `tasks/publish.py` there's a private `_run_single_publish(video_id,
platform, visibility)` that delegates to `publish_video.run`. The
multi-platform tests `patch.object` this function so they can mock per
platform without touching DB / S3. Public API of
`publish_video_all(video_id, platforms, visibility)` is unchanged.

### Buffer endpoint shapes are assumed, not verified
Buffer's published API docs leave some response fields ambiguous (e.g.
`media_id` vs `id`, `service_link` populated for all platforms?). The
publisher uses fallback keys and a default Buffer-app permalink as
`external_url`. Tracked in TODO; first real upload will reveal the
actual shapes and we'll reconcile.

## 2026-05-02 — Phase 5 (YouTube publisher)

### `Publisher` is an ABC, not a Protocol
Concrete subclass + `@abstractmethod` reads better than a `Protocol`
when there's a class attribute (`platform`) that callers depend on.
Trade-off: subclassing instead of duck-typing; trivial.

### YouTube via raw httpx, not google-api-python-client
The official client pulls in `googleapis-common-protos`, `google-auth`,
`google-auth-httplib2`, `httplib2`, etc. For a single resumable upload
+ refresh-token flow, those are overkill. httpx + 50 lines of glue is
easier to test (respx-mockable) and easier to reason about. Swap to
the official client if we hit retry/quota edge cases.

### Resumable upload (not multipart) even for tiny files
Two HTTPS calls (POST snippet → PUT bytes) instead of one multipart PUT.
Slightly slower but cleaner failure mode: a network blip between the
POST and the PUT can be retried without re-sending the metadata.

### Status rollback on `PublishError`
On any publish failure the worker transitions `publishing → approved`
(not `failed`) so a retry is just another `make publish` call. The
error message lands in `videos.failure_reason` for forensics. Trade-off:
the video stays in the operator's "to publish" pile until they
explicitly give up. Right default for a manual-gate v0.

### Idempotency by `(video_id, platform)` UNIQUE
The publisher itself is *not* idempotent (YouTube's API will happily
duplicate uploads). We enforce idempotency in the worker by checking
`Publication` first; the `UniqueConstraint(video_id, platform)` in the
schema catches any race the in-memory check misses.

### YouTube tags: ≤ 500 char total cap; AI + Shorts + brand by default
The metadata builder dedupes and truncates greedily under the 500-char
budget. Default tag set is just three (AI / Shorts / persona.brand) —
the brand carries the niche-specific keyword. Persona schema can grow
a `youtube_tags: list[str]` field later if we need finer control.

### Synthetic-content disclosure: `containsSyntheticMedia=true`
Per YouTube's March-2024 policy. Set on every upload (we always use AI).
Plain-language disclosure also appended to the description for FTC
hygiene.

## 2026-05-02 — Phase 6 (analytics + feedback)

### One-shot ETAs at publish time + beat catch-up
At publish time we `apply_async(eta=...)` three snapshot tasks (t+24h,
t+72h, t+7d). Beat fires `nightly_catchup` at 02:00 UTC to re-snapshot
anything whose latest metric is older than 24h. Belt-and-suspenders:
a worker dying between publish and the t+24h ETA is still covered.

### YouTube Data API only, not Analytics API (yet)
Data API gives `viewCount`, `likeCount`, `commentCount` from the same
OAuth scope we use for upload. `avg_view_duration_sec`,
`retention_curve`, and `ctr` need the *Analytics* API (different
endpoint + scope `yt-analytics.readonly`). Schema reserves those
columns; we write zeros for now and fill them in once we have enough
volume to justify the second OAuth dance. Tracked in TODO.

### Margin proxy = views / cost_cents
Real margin needs YouTube ad-revenue per video (channel-level only via
Data API). `views_per_cent` is intent-aligned: high values mean a
cheap-to-make video with broad reach. Dashboard tints it (≥100 emerald,
≥20 amber, else neutral) so winners pop.

### Learnings live in S3, not in DB
`niches/{niche_id}/learnings_v1.md` is overwritten weekly. The prompt
loader only ever reads the latest; turn on bucket versioning if we
want to audit drift. Trade-off: no DB join to learnings, but no schema
work either for what is effectively a single mutable doc per niche.

### Learnings appended *after* the cached system prompt, not prepended
`system = scripts_v1.md + learnings`. Prepending would invalidate the
prompt cache on every weekly refresh. Appending keeps the leading
prefix stable so the most-cached portion is reused; only the trailing
learnings change weekly.

### Weekly learnings input is JSON, not prose
Sonnet receives a JSON blob with `top_decile` and `bottom_decile`
arrays. Easier to compare structurally, deterministic for caching.
Output is plain markdown so the operator can read
`niches/{id}/learnings_v1.md` directly.

### `weekly_learnings_all` is a fan-out wrapper
Beat schedules a single `weekly_learnings_all` that lists active niches
and fans out one `weekly_learnings` per niche via `apply_async`. New
niches start getting learnings without touching beat config.

## 2026-05-02 — Phase 4 (render)

### Render service is stateless; worker passes everything in the request body
The Remotion service has no DB / S3-read access for inputs — the worker
generates 1h signed URLs (one per scene image + audio), inlines the
captions JSON, and POSTs the whole payload. The render service only
needs S3 *write* credentials to upload the mp4. Trade-off: a few KB
larger request bodies; gain is much simpler render-service deployment
(just an Express app + Remotion bundle, no DB driver).

### Bundle is cached at module level, reset on failure
`bundle()` is the slow part of Remotion (~3-10s on first call). We keep
the resulting serve-URL in a module-level `Promise<string>` so subsequent
requests reuse it. On bundler failure the cache is reset to `null` so
a follow-up request retries cleanly rather than serving the rejected
promise forever.

### Render cost is a flat $0.001/render-second placeholder
We don't have CPU-time pricing for the render box yet, so
`RENDER_COST_PER_SEC_USD = 0.001` in `tasks/render.py` is a SWAG. Re-tune
once we know the box. The `cost_event` records `render_ms` and
`size_bytes` in `meta` so we can backfill if the rate changes.

### CTA fades in over the last 3 seconds, not persistent
Persistent CTA pulls the eye away from the hook + payoff. Fade-in at
T-3s gives the viewer the call-to-action exactly when the video is
about to end. If retention data later says the persistent variant
performs better we can A/B per-niche.

### Captions render in a 6-word sliding window with the active word in `#fbbf24`
Sliding window keeps reading load light and matches what high-retention
shorts on TikTok/Reels do. Active-word highlight is the single biggest
lever for keeping the eye on the screen (gives the brain a moving
target). Color is amber rather than white-on-bold so it pops without
clashing with the hook overlay.

### The render service uploads mp4 directly (not via the worker)
Two simpler paths exist: (1) render service writes to S3, (2) worker
downloads from render service and writes to S3. We picked (1) — the
worker doesn't need to handle a potentially-large mp4 in memory, and
the render service already has the file on disk after `renderMedia`.
Trade-off: render service needs S3 write credentials (it has them via
the same env vars). Same network blast radius either way.

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
