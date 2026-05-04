.PHONY: setup up down install dev worker beat render render-video publish publish-all snapshot learnings produce publish-approved migrate migrate-revision test fmt lint seed trends-fetch trends-cluster trends-pick assets e2e-stub clean

# Pick the available compose CLI. Modern Docker ships `docker compose` (the
# v2 plugin); Colima / Podman / older installs ship the standalone
# `docker-compose` binary. Both accept the compose file we use.
COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

setup:
	bash scripts/setup.sh

up:
	$(COMPOSE) -f infra/docker-compose.yml up -d

down:
	$(COMPOSE) -f infra/docker-compose.yml down

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
	uv run alembic -c infra/alembic.ini upgrade head

migrate-revision:
	uv run alembic -c infra/alembic.ini revision --autogenerate -m "$(m)"

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

assets:
	uv run python -m shortstack_worker.cli assets generate --video-id $(VIDEO)

render-video:
	uv run python -m shortstack_worker.cli render video --video-id $(VIDEO)

publish:
	uv run python -m shortstack_worker.cli publish video --video-id $(VIDEO) --platform $(if $(PLATFORM),$(PLATFORM),youtube_shorts) --visibility $(if $(VISIBILITY),$(VISIBILITY),unlisted)

publish-all:
	uv run python -m shortstack_worker.cli publish all --video-id $(VIDEO) --platforms $(PLATFORMS) --visibility $(if $(VISIBILITY),$(VISIBILITY),unlisted)

snapshot:
	uv run python -m shortstack_worker.cli analytics snapshot --publication-id $(PUBLICATION)

learnings:
	uv run python -m shortstack_worker.cli analytics learnings --niche $(NICHE)

produce:
	uv run python -m shortstack_worker.cli automation daily --niche $(NICHE) $(if $(MAX),--max $(MAX),)

publish-approved:
	uv run python -m shortstack_worker.cli automation publish-approved --niche $(NICHE) $(if $(PLATFORM),--platform $(PLATFORM),) $(if $(VISIBILITY),--visibility $(VISIBILITY),)

NICHE ?= ai-productivity

e2e-stub:
	NICHE=$(NICHE) uv run python scripts/e2e_stub.py

clean:
	$(COMPOSE) -f infra/docker-compose.yml down -v
	rm -rf .venv node_modules apps/*/node_modules apps/*/.next
