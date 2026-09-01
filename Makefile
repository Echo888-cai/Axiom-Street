.PHONY: up down api web lint typecheck test test-all ingest golden migrate prune-snapshots

up:
	docker compose up --build

down:
	docker compose down

api:
	uvicorn services.api.main:app --reload --port 8000

web:
	npm --prefix apps/web run dev

lint:
	ruff check quant services tests
	ruff format --check quant services tests

typecheck:
	mypy quant services
	npm --prefix apps/web exec tsc --noEmit

test:
	pytest tests/unit -q

test-all: lint typecheck test
	npm --prefix apps/web run build

ingest:
	python -m quant.data.ingest_spy

golden:
	pytest -m golden -q

migrate:
	alembic upgrade head

prune-snapshots:
	python -m services.api.prune_snapshots
