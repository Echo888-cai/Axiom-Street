# Axiom Street — Active Plan

> This is the single source for current phase, active work, and future work. Completed implementation detail is intentionally removed; Git history is the archive.

Related documents:

- Product principles: [`VISION.md`](VISION.md)
- Runtime architecture: [`architecture.md`](architecture.md)
- Data sources: [`data-sources.md`](data-sources.md)
- Validation rules: [`validation-gates.md`](validation-gates.md)
- Frontend handoff: [`frontend-handoff.md`](frontend-handoff.md)
- Design system: [`../design-system/axiom-street/MASTER.md`](../design-system/axiom-street/MASTER.md)

## Current state

- Product: `apps/web` is the only product frontend.
- Runtime domains: `services/api`, `services/worker`, `quant`, and `services/agent`.
- Current phase: Phase 8 Portfolio and attribution.
- Phase 5 is closed through P5-4; Phase 6/7 is closed through E6-2 with paper execution and a fail-closed Live readiness guard.
- Current portfolio package: E8-2 is closed; portfolio attribution is available in the product UI, while factor exposure remains explicitly unavailable.

## Active work

| Work package | Status | Deliverable | Verification |
|---|---|---|---|
| Project organization | Closed | Frontend/backend/Agent ownership, active-plan cleanup, architecture diagram | `make test-all` plus focused Agent boundary tests |
| P5-4 guided chat | Closed | Bounded research chat with aggregate-only provider input, async ledger, and honest UI states | Agent isolation tests, API/worker tests, 89 frontend tests, typecheck |
| E6-1 paper execution substrate | Closed | Order/position/fill ledger, risk-gated paper broker seam, idempotency, and reconciliation contract | 15 focused tests; 485 Python tests; 89 frontend tests; mypy/tsc/build |
| E6-2 live readiness guard | Closed | Explicit readiness evidence and a server-side fail-closed activation guard; no external broker calls | 5 focused tests; 490 Python tests; 89 frontend tests; mypy/tsc/build |
| E8-1 portfolio attribution substrate | Closed | Portfolio/strategy allocation ledger, single-period Brinson attribution snapshots, and read-only API contract | 7 focused tests; 497 Python tests; 89 frontend tests; mypy/tsc/build |
| E8-2 portfolio attribution UI and factor evidence | Closed | `/portfolios` reads server-owned allocations and Brinson attribution; unavailable factor exposures have an honest empty state | 3 focused frontend tests; full Python/frontend/typecheck/build suite |

## Future work

| Phase | Scope | Entry condition |
|---|---|---|
| Phase 6/7 | Live remains disabled until paper execution and backtest-to-live reconciliation are measurable | E6-1 paper substrate and reconciliation contract closed |
| Phase 8 | Portfolio and attribution | E6-2 remains closed and Live stays fail-closed |
| Phase 9 | Operational hardening and live safety review | E8-2 is closed; Live Broker remains absent and cannot be enabled by configuration alone |

## Closed work packages

| Package | Closed | Result |
|---|---|---|
| W0–W4 / RC-W2–RC-W4 | 2026-09-07 | Documentation, architecture, frontend, and Phase 4 closure delivered |
| EB-P5 | 2026-09-07 | Observability, credentials, CORS, and Phase 5 entry debt closed |
| P5-1 | 2026-09-07 | Copilot context, provider seam, deterministic panel |
| P5-2 | 2026-09-07 | DeepSeek synthesize path with aggregate-only outbound context |
| P5-3 | 2026-09-07 | Deterministic suggestions and human-confirmed execution |
| P5-4 | 2026-09-08 | Bounded guided chat, aggregate-only provider context, async message ledger, and frontend polling UI |
| E6-1 | 2026-09-08 | Risk-gated paper order execution, idempotency, fills, positions, cash, and reconciliation snapshots |
| E6-2 | 2026-09-08 | Live readiness evidence and activation guard; Live Broker remains intentionally absent |
| E8-1 | 2026-09-08 | Portfolio configuration, server-owned allocations, and reproducible single-period attribution snapshots |
| E8-2 | 2026-09-08 | Portfolio attribution UI, typed API client, navigation entry, and honest factor-exposure empty state |

## Update discipline

1. Work one package at a time.
2. Update this file, the README pointer, and the `.cursor` current-scope pointer when a package closes.
3. Run `rg` for old package/provider wording before committing.
4. Never claim a package is complete without fresh test/build evidence.
