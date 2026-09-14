PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: up down api web lint typecheck test test-all ingest golden migrate prune-snapshots prune-jobs clean e2e-isolated e2e-reset drill-multiworker

up:
	docker compose up --build

down:
	docker compose down

# 隔离 E2E 栈（P1 关闭验收）：独立库/端口/数据，不触碰 axiom-street 主栈。
E2E_COMPOSE := infra/e2e/docker-compose.e2e.yml
E2E_ARGS := -p axiom-e2e -f $(E2E_COMPOSE) --env-file .env.example

e2e-isolated:
	docker-compose $(E2E_ARGS) up -d --build
	cd apps/web && npm run e2e:isolated

e2e-reset:
	docker-compose $(E2E_ARGS) down
	-docker volume rm axiom-e2e_e2e-pgdata
	rm -rf jobs-e2e/* apps/web/test-results

drill-multiworker:
	bash scripts/multi-worker-drill.sh

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

prune-jobs:
	$(PYTHON) -m services.api.prune_jobs --keep-recent 20

clean:
	rm -rf apps/web/.next apps/web/test-results apps/web/playwright-report .pytest_cache .mypy_cache .ruff_cache
	rm -f apps/web/tsconfig.tsbuildinfo
	find quant services tests -type d -name __pycache__ -prune -exec rm -rf {} +
