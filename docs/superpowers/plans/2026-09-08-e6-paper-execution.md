# E6-1 Paper Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a paper-only, risk-gated order/fill/position/reconciliation loop without any live broker capability.

**Architecture:** Keep order validation and position reconstruction in a pure `quant/execution` package. API endpoints only validate scope, enqueue, and read ledgers; the Celery worker reads server-side strategy risk limits, applies `RiskEngine`, and commits one transactional paper execution result.

**Tech Stack:** Python 3.11, SQLAlchemy, Alembic, FastAPI, Celery, pytest, existing `quant.risk.engine.RiskEngine`.

**Spec:** `docs/superpowers/specs/2026-09-08-e6-paper-execution-design.md`

## Global Constraints

- Live broker integrations remain absent and disabled.
- Client payloads never provide risk limits, current exposure, account equity, or risk decisions.
- Invalid risk configuration fails loud; rejected orders never create fills or mutate positions.
- Every schema change uses a real Alembic migration.
- Use TDD: each task starts with a failing test and ends with focused tests plus a commit.

---

### Task 1: Pure paper execution domain

**Files:**
- Create: `quant/execution/__init__.py`
- Create: `quant/execution/paper.py`
- Test: `tests/unit/test_paper_execution.py`

**Interfaces:**
- `PaperOrderCommand` validates `symbol`, `side`, positive finite `quantity` and `simulation_price`, and non-empty idempotency key.
- `PositionState` holds signed quantity, average price, realized P&L, and mark price.
- `rebuild_positions(fills)` reconstructs long-only positions from filled buy/sell rows and raises on oversell.
- `risk_target(...)` converts a requested order into current/target weights and calls `RiskEngine`; it returns an allowed quantity and stable reason.

- [ ] **Step 1: Write failing tests** for command validation, risk cap, long-only oversell, and fill reconstruction.
- [ ] **Step 2: Run `./.venv/bin/python -m pytest tests/unit/test_paper_execution.py -q` and confirm missing-module failures.**
- [ ] **Step 3: Implement the stdlib-only domain types and functions.**
- [ ] **Step 4: Rerun the focused tests and confirm they pass.**
- [ ] **Step 5: Commit `feat: add paper execution domain`.**

### Task 2: Paper ledger models and migration

**Files:**
- Modify: `services/api/models.py`
- Create: `services/api/alembic/versions/0013_paper_execution.py`
- Test: `tests/unit/test_paper_ledger.py`

**Interfaces:**
- Add `PaperOrder`, `PaperFill`, `PaperPosition`, `PaperAccount`, and `PaperReconciliation` models with explicit status enums and uniqueness on `(strategy_id, client_order_id)`.
- Add model tests that create a SQLite schema, enforce idempotency, and persist the foreign-key graph.

- [ ] **Step 1: Write failing model/constraint tests.**
- [ ] **Step 2: Run the focused test and observe missing model/table failure.**
- [ ] **Step 3: Implement models and Alembic upgrade/downgrade.**
- [ ] **Step 4: Run focused ledger tests plus `ruff check/format`.**
- [ ] **Step 5: Commit `feat: add paper execution ledger`.**

### Task 3: Worker transaction and idempotency

**Files:**
- Create: `services/worker/tasks/paper.py`
- Modify: `services/worker/tasks/__init__.py`
- Test: `tests/unit/test_paper_worker.py`

**Interfaces:**
- `execute_paper_order(payload: dict) -> dict` is the only paper execution entry point.
- `run_paper_order_task` is Celery task `paper.execute_order`.
- Worker derives risk configuration from the latest strategy version, loads/creates the paper account, applies the pure domain result, and commits order/fill/position/reconciliation atomically.

- [ ] **Step 1: Write failing worker tests for filled, rejected, duplicate, and failed-risk-config paths.**
- [ ] **Step 2: Run the focused worker tests and observe missing task/model failures.**
- [ ] **Step 3: Implement one transaction boundary and explicit status transitions.**
- [ ] **Step 4: Rerun focused worker plus isolation tests; verify rejected orders have zero fills.**
- [ ] **Step 5: Commit `feat: execute risk-gated paper orders`.**

### Task 4: API contract and read-only ledger queries

**Files:**
- Create: `services/api/routers/paper.py`
- Modify: `services/api/schemas.py`
- Modify: `services/api/main.py`
- Test: `tests/unit/test_paper_api.py`

**Interfaces:**
- `POST /api/v1/paper/orders` validates strategy existence and enqueues `run_paper_order_task.delay(payload.model_dump())`, returning `202`.
- `GET /api/v1/paper/orders`, `/positions`, and `/reconciliation` are read-only and strategy-scoped.
- `PaperOrderIn` contains no risk-limit or account-state fields.

- [ ] **Step 1: Write failing API tests for 404, 422, 202, and read-only response shapes.**
- [ ] **Step 2: Run them and observe missing route/schema failures.**
- [ ] **Step 3: Implement the schemas, router, and registration.**
- [ ] **Step 4: Regenerate `apps/web/openapi.json` and TypeScript types; rerun API tests.**
- [ ] **Step 5: Commit `feat: expose paper execution api`.**

### Task 5: Documentation, full verification, and phase handoff

**Files:**
- Modify: `docs/PLAN.md`, `docs/architecture.md`, `README.md`
- Test: full repository verification

- [ ] **Step 1: Update the plan to mark E6-1 closed only after all focused tests pass.**
- [ ] **Step 2: Document the paper-only limitation and reconciliation flow in the architecture diagram.**
- [ ] **Step 3: Run `make test-all`, inspect the generated OpenAPI diff, and run migration checks.**
- [ ] **Step 4: Commit docs and generated contract only after fresh verification.**
