# ShortStack

AI short-video pipeline for **Trending Tech**. Pulls trends → Claude writes scripts → assets generated → Remotion renders → YouTube Shorts (then IG/TikTok/X/LinkedIn).

## Quickstart

```bash
cp .env.example .env       # fill in keys as you go
make up                    # boot postgres, redis, minio
make install               # uv sync + pnpm install
make dev                   # api :8000, dashboard :3000, render :8787
```

## Layout

```
apps/
  api/                 FastAPI
  dashboard/           Next.js 14 (read-only for now)
  render/              Remotion + Express render service
packages/
  core/                Pydantic schemas, prompts, db, storage, cost
  publishers/          Publisher interface + impls (YouTube first)
workers/               Celery (queues: trends, scripts, assets, render, publish, analytics)
infra/
  docker-compose.yml   postgres + redis + minio
  migrations/          alembic
scripts/               one-off jobs
```

## Phase status

- **Day 1 (today):** skeleton — `make dev` boots all 3 services. No DB models yet.
- Day 2: schemas + alembic migrations + seed
- Day 3: Celery + cost plumbing
- Day 4: trends slice (Reddit) end-to-end
- Day 5: read-only dashboard pages
- Day 6: approval-gate stub + `make e2e-stub`
- Day 7: docs, tests, polish

See `DECISIONS.md` for architectural choices and `TODO.md` for open questions.
