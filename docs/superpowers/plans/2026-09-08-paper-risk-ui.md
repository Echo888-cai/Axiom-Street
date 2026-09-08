# 模拟盘与风控前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将纸面执行台账和服务端风险摘要接入可操作的 `/paper`、`/risk` 页面。

**Architecture:** 新增 `quant/risk/summary.py` 纯风险摘要函数；FastAPI 新增只读风险摘要适配器；前端按现有 domain API、React Query 和 White Studio 组件模式增加纸面执行台与风控页。订单副作用仍只发生在 Worker，前端不维护金融状态副本。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy · Pydantic · pytest · Next.js · React Query · TypeScript · Vitest · Testing Library · Tailwind。

**Spec:** `docs/superpowers/specs/2026-09-08-paper-risk-ui-design.md`

## Global Constraints

- Paper execution remains risk-gated and worker-owned; the API only enqueues orders.
- Live Broker remains absent; `LIVE_BROKER_IMPLEMENTED` stays `False`.
- Missing account/configuration is an explicit unavailable state, never fake zero-valued portfolio data.
- Financial values displayed by the UI come from API responses; the browser does not synthesize fills, equity, or P&L.
- New quant calculations require boundary tests and new API contracts require OpenAPI/type regeneration.

---

### Task 1: Pure risk summary

**Files:**
- Create: `quant/risk/summary.py`
- Test: `tests/unit/test_risk_summary.py`

**Interfaces:**
- Consumes: `RiskLimits`-compatible mapping, optional account values, paper positions, reconciliation status.
- Produces: immutable `RiskSummary` with explicit nullable account fields, exposure ratios, config validity, and blocking reasons.

- [ ] **Step 1: Write failing tests** for no account, invalid config, positive/negative exposure, and zero-equity failure.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/unit/test_risk_summary.py -q`; expect import/collection failure because the module is absent.
- [ ] **Step 3: Implement** the pure dataclass and deterministic calculation using `equity = cash + Σ(quantity × mark_price)` and gross/net exposure divided by positive equity.
- [ ] **Step 4: Run** the focused tests and verify all pass.
- [ ] **Step 5: Commit** `feat: add paper risk summary domain`.

### Task 2: Risk summary API

**Files:**
- Modify: `services/api/schemas.py`
- Create: `services/api/routers/risk.py`
- Modify: `services/api/main.py`
- Test: `tests/unit/test_risk_api.py`
- Regenerate: `apps/web/openapi.json`, `apps/web/src/lib/api-types.gen.ts`

**Interfaces:**
- Consumes: `GET /api/v1/risk/summary?strategy_id=<uuid>` and the pure risk summary function.
- Produces: `RiskSummaryOut` with strategy status, config validity, account metrics, exposure metrics, reconciliation status, and blocking reasons.

- [ ] **Step 1: Write failing API tests** for a valid paper account and a missing account/configuration.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/unit/test_risk_api.py -q`; expect failure because the route/schema is absent.
- [ ] **Step 3: Implement** server-side reads from the latest `StrategyVersion`, `PaperAccount`, `PaperPosition`, and latest `PaperReconciliation`; never accept risk limits from request input.
- [ ] **Step 4: Regenerate OpenAPI and frontend types**, then run focused API tests and mypy.
- [ ] **Step 5: Commit** `feat: expose paper risk summary api`.

### Task 3: Typed paper/risk API clients

**Files:**
- Modify: `apps/web/src/lib/api/types.ts`
- Create: `apps/web/src/lib/api/paper.ts`
- Create: `apps/web/src/lib/api/risk.ts`
- Modify: `apps/web/src/lib/api.ts`
- Tests: `apps/web/src/lib/api/paper.test.ts`, `apps/web/src/lib/api/risk.test.ts`

**Interfaces:**
- Consumes: generated OpenAPI schemas and existing `request` transport.
- Produces: typed `paperApi` and `riskApi` methods used by pages.

- [ ] **Step 1: Write failing client route tests** for order POST and paper/risk GET paths.
- [ ] **Step 2: Run** the two focused Vitest files; expect module/method failures.
- [ ] **Step 3: Implement** typed methods and expose them through the public `api` facade.
- [ ] **Step 4: Run** focused client tests and `npm --prefix apps/web run typecheck`.
- [ ] **Step 5: Commit** `feat: add paper and risk api clients`.

### Task 4: Paper execution desk UI

**Files:**
- Create: `apps/web/src/features/paper/paper-desk.tsx`
- Create: `apps/web/src/features/paper/paper-desk.test.tsx`
- Modify: `apps/web/src/app/paper/page.tsx`
- Modify: `apps/web/src/locales/zh/paper.ts`, `apps/web/src/locales/en/paper.ts`
- Modify: locale aggregators and nav copy as needed

**Interfaces:**
- Consumes: `api.listStrategies`, `paperApi.createOrder`, `paperApi.listOrders`, `paperApi.getPositions`, `paperApi.getReconciliation`.
- Produces: real order form, account/position/order/reconciliation views and explicit loading/error/empty states.

- [ ] **Step 1: Write failing component tests** for strategy selection, order submission, server error rendering, and no-account empty state.
- [ ] **Step 2: Run** the focused component test; expect failure because the desk is absent.
- [ ] **Step 3: Implement** React Query data flow and form with no optimistic financial updates.
- [ ] **Step 4: Run** focused component tests, lint, and typecheck.
- [ ] **Step 5: Commit** `feat: add paper execution desk`.

### Task 5: Risk page UI

**Files:**
- Create: `apps/web/src/features/risk/risk-desk.tsx`
- Create: `apps/web/src/features/risk/risk-desk.test.tsx`
- Modify: `apps/web/src/app/risk/page.tsx`
- Modify: `apps/web/src/locales/zh/risk.ts`, `apps/web/src/locales/en/risk.ts`
- Modify: locale aggregators as needed

**Interfaces:**
- Consumes: `api.listStrategies` and `riskApi.getSummary`.
- Produces: read-only risk summary cards and blocking reasons with no risk mutation controls.

- [ ] **Step 1: Write failing component tests** for healthy summary, blocked reasons, and unavailable account.
- [ ] **Step 2: Run** the focused component test; expect failure because the desk is absent.
- [ ] **Step 3: Implement** strategy selection, summary cards, and honest unavailable/error states.
- [ ] **Step 4: Run** focused tests, full frontend tests, and production build.
- [ ] **Step 5: Commit** `feat: add risk monitoring desk`.

### Task 6: Documentation and package closure

**Files:**
- Modify: `docs/PLAN.md`
- Modify: `docs/architecture.md`
- Modify: `README.md`
- Modify: `.cursor/rules/axiom-street.mdc`

- [ ] **Step 1:** Record the completed paper/risk UI package and exact verification counts.
- [ ] **Step 2:** Run `make test-all` and `git diff --check`.
- [ ] **Step 3:** Review the route/API/doc diff and commit `docs: close paper risk ui package`.
