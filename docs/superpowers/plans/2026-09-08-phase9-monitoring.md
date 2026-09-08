# Phase 9 Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立真实健康状态的后端检查和前端运行监控卡片。

**Architecture:** 后端在 `services/api/health.py` 聚合依赖、Worker 心跳和沙箱策略；健康响应继续使用现有 `HealthOut` 的扩展 `checks` 字典以保持兼容。前端用 typed `healthApi` 查询同一接口，在设置页渲染可读状态。

**Tech Stack:** FastAPI、Redis、SQLAlchemy、Prometheus、React Query、React、Vitest。

**Spec:** `docs/superpowers/specs/2026-09-08-phase9-monitoring-design.md`

## Global Constraints

- 不新增模拟指标，不暴露凭证和完整异常内容。
- 保持 `/health` 和 `/api/v1/health` 路径与旧字段兼容。
- 每个任务先写失败测试，再实现，再运行聚焦测试。

### Task 1: 健康聚合和 Worker 心跳状态

**Files:**
- Modify: `services/api/health.py`
- Modify: `tests/unit/test_multi_symbol.py` or new health unit test

**Interfaces:**
- `collect_health()` returns `checks.worker` and `checks.security`, and status transitions `ok/degraded/down` deterministically.

- [ ] Step 1: Add failing tests for missing/stale worker heartbeat, PostgreSQL failure, and sandbox status.
- [ ] Step 2: Run focused tests and verify failure.
- [ ] Step 3: Implement bounded heartbeat age parsing and security posture reporting.
- [ ] Step 4: Run health-focused tests and mypy.
- [ ] Step 5: Commit `feat: expose phase 9 operational health`.

### Task 2: Typed API and monitoring card

**Files:**
- Create: `apps/web/src/lib/api/health.ts`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/api/types.ts`
- Create: `apps/web/src/features/settings/operations-health-card.tsx`
- Create: `apps/web/src/features/settings/operations-health-card.test.tsx`
- Modify: `apps/web/src/features/settings/settings-desk.tsx`
- Modify: `apps/web/src/locales/zh/common.ts`
- Modify: `apps/web/src/locales/en/common.ts`

- [ ] Step 1: Add failing component tests for healthy, degraded, and API error states.
- [ ] Step 2: Run the focused Vitest file and verify failure.
- [ ] Step 3: Implement typed health client and card, then mount it above the settings cards.
- [ ] Step 4: Run focused tests, frontend typecheck, lint, and build.
- [ ] Step 5: Commit `feat: add operations health monitor`.

### Task 3: Contract regeneration and full verification

**Files:**
- Modify: `apps/web/openapi.json`
- Modify: `apps/web/src/lib/api-types.gen.ts`
- Modify: `docs/PLAN.md`
- Modify: `docs/architecture.md`

- [ ] Step 1: Regenerate OpenAPI types from the API app.
- [ ] Step 2: Run `make test-all`.
- [ ] Step 3: Commit `docs: close phase 9 monitoring package`.
