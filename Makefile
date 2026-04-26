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
	@echo "Phase 0: worker not yet implemented (Day 3)"

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

e2e-stub:
	@echo "Phase 0: e2e-stub not yet implemented (Day 6)"

clean:
	docker compose -f infra/docker-compose.yml down -v
	rm -rf .venv node_modules apps/*/node_modules apps/*/.next
