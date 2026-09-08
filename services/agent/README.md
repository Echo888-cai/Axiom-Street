# Agent domain

`services/agent` owns the server-side Agent domain while preserving the API and
Worker deployment boundaries.

- `copilot/` assembles read-only aggregate context, queries the Copilot ledger,
  renders prompts, and adapts the configured provider.
- `suggestions.py` derives deterministic, whitelist-constrained action cards.
- `services/api/routers/copilot.py` remains the HTTP adapter.
- `services/worker/tasks/copilot.py` remains the asynchronous execution entry
  point and the only place that writes Copilot ledgers.

The provider boundary is aggregate-only. Strategy source, parameter
configuration, and raw market series must not enter Agent context or outbound
provider requests. Copilot ORM writes are limited to the worker's
`_record_insight` and `_record_suggestion` helpers, which write only the
Copilot-owned ledger tables.
