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
- Current phase: Phase 5 AI Copilot; P5-1, P5-2, and P5-3 are closed.
- Next decision: evaluate P5-4 chat shape only after confirming real capability and boundaries.
- Current organization package: make the frontend, backend, and Agent ownership visible in code and documentation.

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
2. Update this file, the README pointer, and the `.cursor` current-scope pointer when a package closes.
3. Run `rg` for old package/provider wording before committing.
4. Never claim a package is complete without fresh test/build evidence.
