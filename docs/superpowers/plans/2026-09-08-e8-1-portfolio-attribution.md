# E8-1 Portfolio Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible portfolio allocation ledger and single-period Brinson attribution snapshots.

**Architecture:** Keep the attribution formula in a pure `quant/portfolio` module. FastAPI owns portfolio configuration and snapshot persistence; the API reads server-side weights, validates submitted period returns, and writes the exact calculation inputs with each snapshot.

**Tech Stack:** Python 3.11, dataclasses, pytest, SQLAlchemy, Alembic, FastAPI, OpenAPI TypeScript codegen.

**Spec:** `docs/superpowers/specs/2026-09-08-e8-1-portfolio-attribution-design.md`

## Global Constraints

- No synthetic market series or external factor data.
- Weights are server-owned and must sum to 1 before attribution.
- Incomplete, duplicate, non-finite, or unmapped strategy returns fail loud.
- Every attribution result stores its calculation inputs.
- Use TDD and a real Alembic migration.

---

### Task 1: Pure attribution engine

**Files:**
- Create: `quant/portfolio/__init__.py`, `quant/portfolio/attribution.py`
- Test: `tests/unit/test_portfolio_attribution.py`

- [ ] Write failing tests for the decomposition and invalid inputs.
- [ ] Run the focused test to confirm the missing-module failure.
- [ ] Implement `compute_brinson_attribution(...)` and immutable result rows.
- [ ] Run tests and commit `feat: add pure portfolio attribution`.

### Task 2: Portfolio ledger models and migration

**Files:**
- Modify: `services/api/models.py`
- Create: `services/api/alembic/versions/0014_portfolios.py`
- Test: `tests/unit/test_portfolio_ledger.py`

- [ ] Write failing schema tests for portfolios, allocations, and immutable snapshots.
- [ ] Implement enums, models, indexes, and migration.
- [ ] Run focused tests and ruff; commit `feat: add portfolio attribution ledger`.

### Task 3: Portfolio API

**Files:**
- Modify: `services/api/schemas.py`, `services/api/main.py`
- Create: `services/api/routers/portfolios.py`
- Test: `tests/unit/test_portfolio_api.py`

- [ ] Write failing tests for CRUD, server-owned weights, unknown strategies, and attribution query.
- [ ] Implement routes and transaction boundaries.
- [ ] Regenerate OpenAPI/types; run focused tests and commit `feat: expose portfolio attribution api`.

### Task 4: Documentation and full verification

**Files:**
- Modify: `docs/PLAN.md`, `docs/architecture.md`, `README.md`

- [ ] Mark E8-1 closed only after fresh full verification.
- [ ] Document that factor exposures and real-time portfolio monitoring remain future work.
- [ ] Run `make test-all` and commit final docs/generated contract.
