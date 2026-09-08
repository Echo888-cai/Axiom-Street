# P5-4 Guided Agent Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scoped, auditable Copilot research conversation without exposing strategy source, raw market data, or write paths.

**Architecture:** API validates scope and enqueues; Worker builds aggregate context, calls the existing provider seam, and records one chat ledger row. The frontend polls the ledger and keeps suggested actions on the existing human-confirmed path.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Celery, DeepSeek OpenAI-compatible SDK, Next.js, React Query, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-08-p5-4-guided-agent-chat-design.md`

## Global Constraints

- No model call without `STREET_DEEPSEEK_API_KEY`.
- No strategy code, config, parameter values, prices, risk limits, or validation writes in Agent outbound context.
- No database writes outside the Worker `_record_chat` helper for the new chat ledger.
- Preserve all existing Copilot routes, task names, Provider behavior, and API response contracts.
- User messages are 1–1200 characters and scoped to a real strategy/backtest.

## Task 1: Chat ledger contract

**Files:**
- Create: `services/api/alembic/versions/0012_copilot_chat_messages.py`
- Modify: `services/api/models.py`
- Modify: `services/api/schemas.py`
- Test: `tests/unit/test_copilot_chat.py`

- [ ] Write tests for `QUEUED`, `DONE`, and `FAILED` chat rows plus empty/1201-character input rejection.
- [ ] Run `.venv/bin/python -m pytest tests/unit/test_copilot_chat.py -q` and confirm the new tests fail for missing model/schema behavior.
- [ ] Add `CopilotChatStatus`, `CopilotChatMessage`, `CopilotChatIn`, `CopilotChatAccepted`, and `CopilotChatOut`.
- [ ] Add Alembic revision `0012` with a strategy foreign key and strategy index.
- [ ] Re-run the focused test until green.
- [ ] Commit with `feat: add copilot chat ledger contract`.

## Task 2: Agent prompt, provider, and read model

**Files:**
- Modify: `services/agent/copilot/prompts.py`
- Modify: `services/agent/copilot/providers.py`
- Modify: `services/agent/copilot/insights.py`
- Modify: `tests/unit/test_copilot_providers.py`
- Modify: `tests/unit/test_copilot_context.py`

- [ ] Add failing tests for `build_chat_messages`, Provider `chat`, disabled/no-outbound behavior, empty output, and newest-first chat queries.
- [ ] Run the focused tests and confirm the expected missing-method failures.
- [ ] Implement the bounded system prompt, Provider protocol method, Noop/DeepSeek `chat`, and `list_chat_messages`.
- [ ] Run the focused tests plus `tests/unit/test_copilot_isolation.py`.
- [ ] Commit with `feat: add bounded copilot chat provider`.

## Task 3: API and Worker execution path

**Files:**
- Modify: `services/api/routers/copilot.py`
- Modify: `services/worker/tasks/copilot.py`
- Modify: `services/worker/tasks/__init__.py`
- Modify: `tests/unit/test_copilot_chat.py`
- Modify: `tests/unit/test_copilot_isolation.py`

- [ ] Add failing tests for API `202/404/422/503`, Worker DONE/FAILED rows, and the single `_record_chat` write point.
- [ ] Run the focused test and confirm routes/task are missing.
- [ ] Add `GET /copilot/chat`, enqueue-only `POST /copilot/chat`, `execute_chat`, `run_chat_task`, and `_record_chat`; register Celery task `copilot.chat`.
- [ ] Run focused chat and isolation tests until green.
- [ ] Commit with `feat: add copilot chat enqueue and worker task`.

## Task 4: Frontend guided chat block

**Files:**
- Modify: `apps/web/src/lib/api/copilot.ts`
- Modify: `apps/web/src/lib/api/types.ts`
- Modify: `apps/web/src/components/copilot/copilot-panel.tsx`
- Create: `apps/web/src/components/copilot/chat-block.tsx`
- Create: `apps/web/src/components/copilot/chat-block.test.tsx`
- Modify: `apps/web/src/locales/en/copilot.ts`
- Modify: `apps/web/src/locales/zh/copilot.ts`

- [ ] Add failing tests for quick prompts, submit payload, polling, done/failed states, disabled provider, and privacy note.
- [ ] Run `npm --prefix apps/web run test -- src/components/copilot/chat-block.test.tsx` and confirm the expected missing-component failure.
- [ ] Implement typed `listChat`/`chat`, `ChatBlock`, two-second polling, and translated copy; mount after `InsightBlock`.
- [ ] Run the component test, TypeScript, and lint.
- [ ] Commit with `feat: add guided copilot chat panel`.

## Task 5: Close P5-4 and open the execution roadmap

**Files:**
- Modify: `docs/PLAN.md`
- Modify: `README.md`
- Modify: `.cursor/rules/axiom-street.mdc`
- Modify: `apps/web/openapi.json`
- Modify: `apps/web/src/lib/api-types.gen.ts`

- [ ] Regenerate OpenAPI types and confirm no unreviewed API diff.
- [ ] Mark Project organization and P5-4 closed; make Phase 6/7 the active roadmap.
- [ ] Run `make test-all` and OpenAPI codegen idempotence checks.
- [ ] Commit with `docs: close p5-4 and open execution phase roadmap`.
