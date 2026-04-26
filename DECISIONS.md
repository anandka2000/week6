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
