# 组合写入工作流 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将组合创建、策略权重配置和单期收益提交接入 `/portfolios`。

**Architecture:** 扩展组合 domain API client 和现有 `PortfolioAttribution` feature；React Query mutation 成功后失效组合、配置和归因查询。归因表单只发送收益输入，服务端按生效日期读取权重并计算结果。

**Tech Stack:** FastAPI · Pydantic · Next.js · React Query · TypeScript · Vitest · Testing Library。

**Spec:** `docs/superpowers/specs/2026-09-08-portfolio-write-ui-design.md`

## Global Constraints

- Portfolio weights remain server-owned for attribution.
- No fake portfolio returns, P&L, or attribution values.
- Existing immutable same-date attribution conflict behavior remains unchanged.
- Existing read-only attribution UI and factor-exposure empty state must remain visible.
- All new API client and UI behavior uses failing tests first.

---

### Task 1: Typed portfolio write API client

**Files:**
- Modify: `apps/web/src/lib/api/portfolios.ts`
- Test: `apps/web/src/lib/api/portfolios.test.ts`

**Interfaces:**
- Consumes: generated `PortfolioCreate`, `PortfolioAllocationIn`, and `PortfolioAttributionIn` shapes.
- Produces: `createPortfolio`, `createAllocation`, and `createAttribution` methods on `portfoliosApi`.

- [ ] **Step 1: Write failing route/body tests** for the three POST methods.
- [ ] **Step 2: Run** the focused Vitest file; expect method-not-defined failures.
- [ ] **Step 3: Implement** typed POST methods with encoded portfolio IDs and JSON bodies.
- [ ] **Step 4: Run** the focused Vitest file and TypeScript check.
- [ ] **Step 5: Commit** `feat: add portfolio write api client`.

### Task 2: Create portfolio form

**Files:**
- Modify: `apps/web/src/features/portfolio/portfolio-attribution.tsx`
- Modify: `apps/web/src/features/portfolio/portfolio-attribution.test.tsx`
- Modify: `apps/web/src/locales/zh/portfolio.ts`, `apps/web/src/locales/en/portfolio.ts`

**Interfaces:**
- Consumes: `api.createPortfolio`, `api.listPortfolios`.
- Produces: a form that creates a portfolio, selects it, and refreshes the page state.

- [ ] **Step 1: Write failing component tests** for creating a portfolio and rendering a server error.
- [ ] **Step 2: Run** the focused component test; expect missing form/action failures.
- [ ] **Step 3: Implement** mutation state, fields, invalidation, and error copy.
- [ ] **Step 4: Run** focused tests and TypeScript check.
- [ ] **Step 5: Commit** `feat: add portfolio creation form`.

### Task 3: Allocation form

**Files:**
- Modify: `apps/web/src/features/portfolio/portfolio-attribution.tsx`
- Modify: `apps/web/src/features/portfolio/portfolio-attribution.test.tsx`
- Modify: locale portfolio files

**Interfaces:**
- Consumes: `api.listStrategies`, `api.createAllocation`, `api.listPortfolioAllocations`.
- Produces: strategy/weight/date form, weight total indicator, and server error state.

- [ ] **Step 1: Write failing component tests** for allocation POST and weight-total display.
- [ ] **Step 2: Run** focused test; expect absent form/action failures.
- [ ] **Step 3: Implement** strategy lookup, allocation mutation, invalidation, and total warning.
- [ ] **Step 4: Run** focused tests, lint, and typecheck.
- [ ] **Step 5: Commit** `feat: add portfolio allocation form`.

### Task 4: Attribution input form

**Files:**
- Modify: `apps/web/src/features/portfolio/portfolio-attribution.tsx`
- Modify: `apps/web/src/features/portfolio/portfolio-attribution.test.tsx`
- Modify: locale portfolio files

**Interfaces:**
- Consumes: active allocation rows, `api.createAttribution`, and `api.listPortfolioAttribution`.
- Produces: per-strategy return inputs, as-of date, server-owned weight submission, and refresh of latest attribution.

- [ ] **Step 1: Write failing component tests** asserting the POST body includes returns but no `weight` fields.
- [ ] **Step 2: Run** focused test; expect absent attribution form/action failures.
- [ ] **Step 3: Implement** date/return form and mutation with duplicate/error feedback.
- [ ] **Step 4: Run** all portfolio component/client tests and production build.
- [ ] **Step 5: Commit** `feat: add portfolio attribution input form`.

### Task 5: Documentation and package closure

**Files:**
- Modify: `docs/PLAN.md`
- Modify: `docs/architecture.md`
- Modify: `README.md`

- [ ] **Step 1:** Record P9-2 closure and exact verification counts.
- [ ] **Step 2:** Run `make test-all` and `git diff --check`.
- [ ] **Step 3:** Commit `docs: close portfolio write ui package`.
