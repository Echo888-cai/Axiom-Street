# Project Organization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize Axiom Street into clear frontend, backend, and Agent ownership while reducing `docs/PLAN.md` to the active roadmap and preserving all runtime/API/deployment contracts.

**Architecture:** Keep `apps/web`, `services/api`, `services/worker`, and `quant` as their existing runtime boundaries. Move the Agent domain from `services/api/services/copilot` and `services/api/services/suggestions.py` into `services/agent`, while leaving HTTP adapters in `services/api` and Celery execution/ledger writes in `services/worker`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Celery, Next.js 15, TypeScript, OpenAPI TypeScript, Ruff, Mypy, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-07-project-organization-design.md`

## Global Constraints

- Do not change HTTP paths, OpenAPI schemas, database tables, Alembic revisions, Celery task names, or frontend API methods.
- `services/api` remains the only HTTP/database write adapter; `services/worker` remains the only Docker/LEAN execution process.
- `services/agent` may expose only read-only context/ledger queries and constrained provider calls; model input remains aggregate statistics or whitelist candidate metadata.
- Copilot ORM writes remain limited to `_record_insight` and `_record_suggestion` in `services/worker/tasks/copilot.py`.
- `quant` must not import FastAPI, Celery, SQLAlchemy, or `services.agent`.
- Do not add chat UI, new Agent capability, provider behavior, database schema, or quant-calculation changes.
- Completed work packages are removed from the active plan body; Git history is the only archive.
- Every task ends with its own targeted verification and commit.

---

## File Map

### Agent domain files

- Create: `services/agent/__init__.py` — package boundary with no write API exports.
- Create: `services/agent/copilot/__init__.py` — read-only Copilot service exports.
- Move: `services/api/services/copilot/context.py` → `services/agent/copilot/context.py`.
- Move: `services/api/services/copilot/insights.py` → `services/agent/copilot/insights.py`.
- Move: `services/api/services/copilot/prompts.py` → `services/agent/copilot/prompts.py`.
- Move: `services/api/services/copilot/providers.py` → `services/agent/copilot/providers.py`.
- Move: `services/api/services/suggestions.py` → `services/agent/suggestions.py`.
- Create: `services/agent/README.md` — Agent inputs/outputs, privacy, and write boundaries.
- Delete after migration: `services/api/services/copilot/`, `services/api/services/suggestions.py`.

### Adapters and tests

- Modify: `services/api/routers/copilot.py` — import Agent services while remaining HTTP-only.
- Modify: `services/worker/tasks/copilot.py` — import Agent services while retaining task names and ledger write helpers.
- Modify: `services/worker/tasks/__init__.py` — keep task registration and public task aliases.
- Modify: `tests/unit/test_copilot_isolation.py` — scan `services/agent` and retain all isolation checks.
- Modify: `tests/unit/test_copilot_context.py`, `tests/unit/test_copilot_providers.py`, `tests/unit/test_copilot_synthesize.py`, `tests/unit/test_copilot_suggest.py`, `tests/unit/test_suggestions.py` — update imports only.

### Documentation

- Replace: `docs/PLAN.md` — active plan only, with a compact completed-work table.
- Modify: `docs/architecture.md` — repository layout, dependency rules, and Mermaid diagram.
- Modify: `docs/frontend-handoff.md` — frontend/Agent boundary and API-only integration statement.
- Modify: `README.md` — remove stale Anthropic/P5-2 status and point to the active plan.
- Modify: `.cursor/rules/axiom-street.mdc` — add `services/agent` ownership without duplicating status.

## Task 1: Create the Agent package and move read-only domain code

**Files:**
- Create: `services/agent/__init__.py`
- Create: `services/agent/copilot/__init__.py`
- Move: `services/api/services/copilot/context.py` → `services/agent/copilot/context.py`
- Move: `services/api/services/copilot/insights.py` → `services/agent/copilot/insights.py`
- Move: `services/api/services/copilot/prompts.py` → `services/agent/copilot/prompts.py`
- Move: `services/api/services/copilot/providers.py` → `services/agent/copilot/providers.py`
- Move: `services/api/services/suggestions.py` → `services/agent/suggestions.py`
- Create: `services/agent/README.md`
- Test: `tests/unit/test_copilot_isolation.py`

**Interfaces:**
- Produces the same callables currently imported from `services.api.services.copilot`: `build_context`, `get_provider`, `latest_suggestion`, `list_insights`.
- Produces `services.agent.suggestions.derive_suggestions` and `CARD_KEYS` with unchanged signatures and values.
- Does not change any API response or provider method signature.

- [ ] **Step 1: Add the new package boundaries before moving implementations.**

Create `services/agent/__init__.py` with a package docstring only. Create `services/agent/copilot/__init__.py` with imports that expose the existing four read-only callables:

```python
"""Agent domain services with no HTTP or database write entry points."""
```

```python
"""Read-only Copilot services; writes belong to worker ledger helpers."""

from services.agent.copilot.context import build_context
from services.agent.copilot.insights import latest_suggestion, list_insights
from services.agent.copilot.providers import get_provider

__all__ = ["build_context", "get_provider", "latest_suggestion", "list_insights"]
```

Create `services/agent/README.md` describing the read-only context projection, whitelist-only suggestion cards, provider privacy boundary, and the only two worker ledger write helpers.

- [ ] **Step 2: Move the implementation files without changing their contents.**

Run:

```bash
git mv services/api/services/copilot/context.py services/agent/copilot/context.py
git mv services/api/services/copilot/insights.py services/agent/copilot/insights.py
git mv services/api/services/copilot/prompts.py services/agent/copilot/prompts.py
git mv services/api/services/copilot/providers.py services/agent/copilot/providers.py
git mv services/api/services/suggestions.py services/agent/suggestions.py
```

Remove the now-empty `services/api/services/copilot` directory after confirming `git status --short` reports the four files as renames.

- [ ] **Step 3: Update only internal Agent imports.**

Change imports inside the moved files and `services/agent/copilot/__init__.py` from `services.api.services.copilot.*` to `services.agent.copilot.*`. Do not change imports of `services.api.models`, `services.api.settings`, `quant.*`, or SQLAlchemy; those are existing dependency directions.

- [ ] **Step 4: Run the import and boundary tests before changing adapters.**

Run:

```bash
.venv/bin/python -c "from services.agent.copilot import build_context, get_provider; from services.agent.suggestions import CARD_KEYS, derive_suggestions; print(build_context.__name__, get_provider.__name__, len(CARD_KEYS), derive_suggestions.__name__)"
.venv/bin/python -m pytest tests/unit/test_copilot_isolation.py -q
```

Expected: the import command exits 0; the isolation test may still fail only because its scanner points to the old path. No moved module may raise an import error.

- [ ] **Step 5: Commit the domain relocation.**

```bash
git add -A services/agent services/api/services/copilot services/api/services/suggestions.py
git commit -m "refactor: move copilot domain into agent package"
```

## Task 2: Rewire API, Worker, and boundary tests

**Files:**
- Modify: `services/api/routers/copilot.py`
- Modify: `services/worker/tasks/copilot.py`
- Modify: `services/worker/tasks/__init__.py`
- Modify: `tests/unit/test_copilot_isolation.py`
- Modify: `tests/unit/test_copilot_context.py`
- Modify: `tests/unit/test_copilot_providers.py`
- Modify: `tests/unit/test_copilot_synthesize.py`
- Modify: `tests/unit/test_copilot_suggest.py`
- Modify: `tests/unit/test_suggestions.py`

**Interfaces:**
- `services/api/routers/copilot.py` continues to expose the existing `/api/v1/copilot/*` routes.
- `services/worker/tasks/copilot.py` continues to register `copilot.synthesize` and `copilot.suggest`.
- The isolation scanner covers every `*.py` under `services/agent/copilot`, the Agent suggestion module, the Router, and the Worker task.

- [ ] **Step 1: Update the API Router imports.**

Replace the two imports in `services/api/routers/copilot.py` with:

```python
from services.agent import copilot as copilot_service
from services.agent import suggestions as suggestions_service
```

Update the existing `derive_suggestions(...)` call sites to `suggestions_service.derive_suggestions(...)`. Leave route decorators, response models, status codes, enqueue calls, and provider checks unchanged.

- [ ] **Step 2: Update Worker imports while preserving the write boundary.**

In `services/worker/tasks/copilot.py`, replace the old imports with:

```python
from services.agent.copilot.context import build_context
from services.agent.copilot.providers import CopilotProviderError, get_provider
from services.agent.suggestions import derive_suggestions
```

Do not move the Worker task file or modify `_record_insight`, `_record_suggestion`, Celery decorators, or task names.

- [ ] **Step 3: Update the isolation scanner to the real Agent location.**

Change its path constants to:

```python
AGENT_DIR = ROOT / "services" / "agent"
COPILOT_DIR = AGENT_DIR / "copilot"
SUGGESTIONS_FILE = AGENT_DIR / "suggestions.py"
```

Keep `ROUTER_FILE`, `TASK_FILE`, forbidden modules, forbidden calls, forbidden columns, ledger helper names, and all assertions unchanged except for expected import module names. Update test messages/docstrings that explicitly claim suggestions live under `services/api/services`.

- [ ] **Step 4: Update unit-test imports and monkeypatch targets.**

Replace `services.api.services.copilot` with `services.agent.copilot` and `services.api.services.suggestions` with `services.agent.suggestions` in the five listed test files. Change string monkeypatch targets such as `services.worker.tasks.copilot.get_provider` only if their target is the moved provider; keep Worker task targets unchanged.

- [ ] **Step 5: Run the focused backend suite and API contract smoke check.**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_copilot_isolation.py tests/unit/test_copilot_context.py tests/unit/test_copilot_providers.py tests/unit/test_copilot_synthesize.py tests/unit/test_copilot_suggest.py tests/unit/test_suggestions.py -q
.venv/bin/python -c "from services.api.main import app; paths = {route.path for route in app.routes}; assert '/api/v1/copilot/context' in paths and '/api/v1/copilot/suggest' in paths; print('copilot routes intact')"
```

Expected: all focused tests pass and both existing Copilot routes are present.

- [ ] **Step 6: Commit the adapter and test updates.**

```bash
git add services/api/routers/copilot.py services/worker/tasks/copilot.py services/worker/tasks/__init__.py tests/unit/test_copilot_isolation.py tests/unit/test_copilot_context.py tests/unit/test_copilot_providers.py tests/unit/test_copilot_synthesize.py tests/unit/test_copilot_suggest.py tests/unit/test_suggestions.py
git commit -m "refactor: rewire api and worker to agent domain"
```

## Task 3: Replace the historical plan with the active plan

**Files:**
- Replace: `docs/PLAN.md`
- Modify: `README.md`
- Modify: `.cursor/rules/axiom-street.mdc`

**Interfaces:**
- `docs/PLAN.md` remains the single status/phase source referenced by README and Cursor rules.
- README status text must not independently name an obsolete provider or closed work package.

- [ ] **Step 1: Write the compact active plan.**

Replace `docs/PLAN.md` with these exact sections:

```markdown
# Axiom Street — Active Plan

> This is the single source for current phase, active work, and future work. Completed implementation detail is intentionally removed; Git history is the archive.

## Current state

- Product: `apps/web` is the only product frontend.
- Runtime domains: `services/api`, `services/worker`, `quant`, and `services/agent`.
- Current phase: Phase 5 AI Copilot; P5-1, P5-2, and P5-3 are closed.
- Next decision: evaluate P5-4 chat shape only after confirming real capability and boundaries.

## Active work

| Work package | Status | Deliverable | Verification |
|---|---|---|---|
| Project organization | In progress | Frontend/backend/Agent ownership, active-plan cleanup, architecture diagram | `make test-all` plus focused Agent boundary tests |
| P5-4 chat shape | Not started | Design decision only; no UI until real capability is approved | Design review and boundary review |

## Future work

| Phase | Scope | Entry condition |
|---|---|---|
| Phase 6/7 | Paper and Live, including backtest-to-live reconciliation | Project organization closed; execution safety design approved |
| Phase 8 | Portfolio and attribution | Phase 6/7 reconciliation is measurable |

## Closed work packages

| Package | Closed | Result |
|---|---|---|
| W0–W4 / RC-W2–RC-W4 | 2026-09-07 | Documentation, architecture, frontend, and Phase 4 closure delivered |
| EB-P5 | 2026-09-07 | Observability, credentials, CORS, and Phase 5 entry debt closed |
| P5-1 | 2026-09-07 | Copilot context, provider seam, deterministic panel |
| P5-2 | 2026-09-07 | DeepSeek synthesize path with aggregate-only outbound context |
| P5-3 | 2026-09-07 | Deterministic suggestions and human-confirmed execution |

## Update discipline

1. Work one package at a time.
2. Update this file, README pointer, and `.cursor/rules` current-scope pointer when a package closes.
3. Run `rg` for old package/provider wording before committing.
4. Never claim a package is complete without fresh test/build evidence.
```

The replacement must not contain the old long-form W0–W4/P5 execution journal, old Anthropic wording, or duplicate historical audit narrative.

- [ ] **Step 2: Make README and Cursor rules point to the new source of truth.**

In `README.md`, change the current status row to state only that Phase 5 P5-1/P5-2/P5-3 are closed and the next scope is described in `docs/PLAN.md`; remove the phrase `P5-2 Anthropic`.

In `.cursor/rules/axiom-street.mdc`, keep the phase pointer concise, add the rule that `services/agent` owns Agent domain logic, and preserve the existing single-source-of-truth rule without copying a second status table.

- [ ] **Step 3: Verify plan consistency.**

Run:

```bash
! rg -n "P5-2 Anthropic|下一包 P5-2|services/api/services/copilot|services/api/services/suggestions" README.md docs .cursor services tests
rg -n "docs/PLAN\.md|services/agent|Current phase|当前阶段" README.md docs/PLAN.md .cursor/rules/axiom-street.mdc docs/architecture.md
```

Expected: the first command finds no stale active references; the second shows the new active plan and Agent ownership references.

- [ ] **Step 4: Commit the plan cleanup.**

```bash
git add docs/PLAN.md README.md .cursor/rules/axiom-street.mdc
git commit -m "docs: consolidate active engineering plan"
```

## Task 4: Update architecture and ownership documentation

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/frontend-handoff.md`
- Create: `services/agent/README.md` from Task 1

**Interfaces:**
- Documentation must describe the same dependency directions as the moved code and tests.
- Mermaid diagram must show Web → API, API → Agent/Worker, Worker → LEAN/quant, Agent → constrained Provider, and API/Worker → PostgreSQL.

- [ ] **Step 1: Update the repository layout table and architecture diagram.**

In `docs/architecture.md`, add `services/agent` to the repository layout table. Replace the old top-level runtime diagram with the Mermaid diagram from the approved design, keeping the existing quant data-flow and safety invariants below it.

- [ ] **Step 2: Document Agent boundaries in architecture prose.**

Add a section that states:

```markdown
### Agent domain

`services/agent` owns Copilot context assembly, provider adapters, prompts, insight queries, and deterministic suggestion derivation. API routes adapt HTTP requests; Worker tasks own asynchronous execution and the only two Copilot ledger write helpers. Agent inputs are aggregate facts or whitelist suggestion metadata; strategy source, parameter configuration, and raw market series do not cross the provider boundary.
```

Keep the existing `quant/` isolation and `API ↛ Docker` rules unchanged.

- [ ] **Step 3: Clarify the frontend handoff.**

In `docs/frontend-handoff.md`, add that `apps/web/src/components/copilot` and `apps/web/src/lib/api/copilot.ts` are frontend presentation/API-client code, while Agent behavior is owned by `services/agent` and is consumed only through documented API endpoints.

- [ ] **Step 4: Run documentation and diagram reference checks.**

Run:

```bash
rg -n "services/agent|Copilot|Agent domain|mermaid|flowchart" docs README.md .cursor/rules/axiom-street.mdc
! rg -n "P5-2 Anthropic|services/api/services/copilot|services/api/services/suggestions" docs README.md .cursor/rules/axiom-street.mdc
```

Expected: the new Agent ownership and diagram references are present; stale paths/provider wording are absent.

- [ ] **Step 5: Commit architecture documentation.**

```bash
git add docs/architecture.md docs/frontend-handoff.md services/agent/README.md
git commit -m "docs: describe frontend backend and agent boundaries"
```

## Task 5: Full verification and final diff audit

**Files:**
- Verify all changed files from Tasks 1–4.

- [ ] **Step 1: Confirm no old import path remains.**

Run:

```bash
! rg -n "services\.api\.services\.copilot|services\.api\.services\.suggestions|services/api/services/copilot|services/api/services/suggestions" --glob '!docs/superpowers/specs/**' --glob '!docs/superpowers/plans/**' .
```

Expected: no output and exit 0.

- [ ] **Step 2: Run the complete Python verification.**

Run:

```bash
make lint
make typecheck
make test
```

Expected: Ruff check/format, Mypy, and the complete `tests/unit` suite exit 0.

- [ ] **Step 3: Run the complete frontend verification.**

Run:

```bash
npm --prefix apps/web run typecheck
npm --prefix apps/web run test
npm --prefix apps/web run lint
npm --prefix apps/web run build
```

Expected: TypeScript, Vitest, ESLint, and Next production build exit 0.

- [ ] **Step 4: Verify OpenAPI codegen is unchanged.**

Run:

```bash
npm --prefix apps/web run codegen:types
git diff --exit-code -- apps/web/src/lib/api-types.gen.ts apps/web/openapi.json
```

Expected: code generation exits 0 and produces no diff.

- [ ] **Step 5: Audit the final diff and status.**

Run:

```bash
git status --short --branch
git diff HEAD~4..HEAD --stat
git log --oneline -5
```

Confirm the diff contains only the Agent relocation, adapter/test import updates, active-plan cleanup, architecture documentation, and approved design/plan files. If the number of commits differs because a task was combined, inspect the actual paths rather than relying on the `HEAD~4` range.

- [ ] **Step 6: Commit only if verification changes generated tracked files.**

If codegen or formatting changed a tracked file, review it and create a focused commit:

```bash
git add apps/web/src/lib/api-types.gen.ts
git commit -m "chore: refresh generated project metadata"
```

If no generated files changed, leave the verified tree clean without an empty commit.
