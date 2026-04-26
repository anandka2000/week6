# ShortStack

AI short-video pipeline for **Trending Tech**.

```
trends  →  cluster + score  →  pick  →  script  →  assets  →  render  →  publish  →  metrics
 (1)         (1)               (1)      (2)        (3)       (4)       (5)        (6)
```

## Quickstart

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

## Try the trend slice

```bash
make trends-fetch    NICHE=ai-productivity   # Reddit hot.json -> trends table
make trends-cluster  NICHE=ai-productivity   # Haiku scores 1-10  (needs ANTHROPIC_API_KEY)
make trends-pick     NICHE=ai-productivity   # consume the highest-scored trend
make e2e-stub        NICHE=ai-productivity   # all of the above + draft a pending_review video
```

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

| Day | Phase | Status | Notes |
|---|---|---|---|
| 1 | Skeleton | done | services boot |
| 2 | Schemas + DB | done | 8 tables, alembic 0001 |
| 3 | Celery + cost | done | 6 queues, pricing table, structlog |
| 4 | Trends (Reddit) | done | YouTube + GTrends sources are TODO |
| 5 | Dashboard | done | read-only |
| 6 | Approval gate | done | `make e2e-stub` works |
| 7 | Polish | done | this README |

Next up: **Phase 2** — Sonnet script generation with cached hook-framework prompt. Tracked in TODO.md. See DECISIONS.md before changing anything material.

## Useful URLs (local)

- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:3000
- Review queue: http://localhost:3000/review
- MinIO console: http://localhost:9001 (login `shortstack` / `shortstack-dev-secret`)
