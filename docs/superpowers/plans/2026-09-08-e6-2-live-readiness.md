# E6-2 Live Readiness Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose an auditable, fail-closed Live readiness check while keeping all real broker access disabled.

**Architecture:** A pure readiness evaluator receives explicit evidence and returns stable reason codes. The API assembles validation, risk-config, paper-reconciliation, and feature-flag evidence; the activation endpoint rejects every current request and never enqueues external execution.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pytest, existing validation and paper ledgers.

**Spec:** `docs/superpowers/specs/2026-09-08-e6-2-live-readiness-design.md`

## Global Constraints

- `broker_implemented` is false until a separately reviewed Broker adapter exists.
- No Live endpoint may call an external service or change `Strategy.status`.
- The evaluator must report all blocking reason codes, not only the first one.
- Use TDD and keep OpenAPI generated from the FastAPI app.

---

### Task 1: Pure readiness evaluator

**Files:**
- Create: `quant/execution/readiness.py`
- Test: `tests/unit/test_live_readiness.py`

- [ ] Write a failing test for all blocking reasons and a passing evidence set.
- [ ] Run the focused test and observe the missing-module failure.
- [ ] Implement `evaluate_live_readiness(...)` with stable reason codes.
- [ ] Run focused tests and commit `feat: add live readiness evaluator`.

### Task 2: Readiness API and activation guard

**Files:**
- Create: `services/api/routers/live.py`
- Modify: `services/api/schemas.py`, `services/api/main.py`
- Test: `tests/unit/test_live_api.py`

- [ ] Write failing tests for readiness evidence, missing strategy, and fail-closed activation.
- [ ] Implement read-only evidence assembly and `POST /live/activate` returning structured 409.
- [ ] Regenerate OpenAPI/TypeScript types and run focused tests.
- [ ] Commit `feat: expose fail-closed live guard`.

### Task 3: Documentation and verification

**Files:**
- Modify: `docs/PLAN.md`, `docs/architecture.md`, `README.md`

- [ ] Mark E6-2 closed only after full verification and state explicitly that Live Broker is absent.
- [ ] Run `make test-all` and inspect the OpenAPI diff.
- [ ] Commit documentation after fresh evidence.
