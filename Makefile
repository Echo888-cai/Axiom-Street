PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: up down api web lint typecheck test test-all ingest golden migrate prune-snapshots

up:
	docker compose up --build

down:
	docker compose down

api:
	$(PYTHON) -m uvicorn services.api.main:app --reload --port 8000

web:
	npm --prefix apps/web run dev

lint:
	$(PYTHON) -m ruff check quant services tests
	$(PYTHON) -m ruff format --check quant services tests

typecheck:
	$(PYTHON) -m mypy quant services
	npm --prefix apps/web run typecheck

test:
	$(PYTHON) -m pytest tests/unit -q

test-all: lint typecheck test
	npm --prefix apps/web run test
	npm --prefix apps/web run lint
	npm --prefix apps/web run build

ingest:
	$(PYTHON) -m quant.data.ingest.cli

golden:
	$(PYTHON) -m pytest -m golden -q

migrate:
	$(PYTHON) -m alembic upgrade head

prune-snapshots:
	$(PYTHON) -m services.api.prune_snapshots
