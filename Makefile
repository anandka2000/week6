.PHONY: up down install dev worker render migrate test fmt lint seed e2e-stub clean

up:
	docker compose --env-file .env -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down

install:
	uv sync
	pnpm install

dev:
	@trap 'kill 0' INT TERM EXIT; \
	(cd apps/api && uv run uvicorn shortstack_api.main:app --reload --port 8000) & \
	(cd apps/dashboard && pnpm dev) & \
	(cd apps/render && pnpm dev) & \
	wait

worker:
	uv run celery -A shortstack_worker.celery_app worker --loglevel=info \
	    -Q trends,scripts,assets,render,publish,analytics

beat:
	uv run celery -A shortstack_worker.celery_app beat --loglevel=info

render:
	cd apps/render && pnpm dev

migrate:
	cd infra && uv run alembic upgrade head

migrate-revision:
	cd infra && uv run alembic revision --autogenerate -m "$(m)"

test:
	uv run pytest

fmt:
	uv run ruff format .

lint:
	uv run ruff check .

seed:
	uv run python scripts/seed_niches.py

trends-fetch:
	uv run python -m shortstack_worker.cli trends fetch --niche $(NICHE)

trends-cluster:
	uv run python -m shortstack_worker.cli trends cluster --niche $(NICHE)

trends-pick:
	uv run python -m shortstack_worker.cli trends pick --niche $(NICHE)

NICHE ?= ai-productivity

e2e-stub:
	NICHE=$(NICHE) uv run python scripts/e2e_stub.py

clean:
	docker compose -f infra/docker-compose.yml down -v
	rm -rf .venv node_modules apps/*/node_modules apps/*/.next
