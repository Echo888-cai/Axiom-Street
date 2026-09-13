# Research workspace

## Direction

The September 12 brief asks for a simpler sidebar, stronger visual hierarchy,
better financial typography, purposeful brand copy, and a maintainable Agent
architecture. Work continues in the existing checkout to preserve the ongoing
frontend edits. Execution status and checks belong in `docs/PLAN.md`.

Use an ink-blue research introduction against warm light reading surfaces.
Keep four primary destinations visible; secondary library and execution tools
expand on demand and reveal the active route. Consolidate workspace and health
in one footer. Put the hypothesis/evidence message beside the research flow,
and the short brand promise in the page footer. Use aligned monospace numbers,
quiet dividers and semantic colors; never draw invented performance curves.

## Implementation sequence

1. Navigation: test secondary disclosure and deep links, simplify the sidebar,
   and verify desktop, collapsed and mobile navigation.
2. Research surfaces: add an introduction and actual status counts to the
   strategy collection, tighten rows, restyle the overview hero and metric
   strip. Test that unavailable data cannot display cached figures as current.
3. Agent read model: reject unsupported resources, aggregate trial counts and
   duplicate hashes in SQL, and preserve family/snapshot semantics. Run context,
   provider, suggestions and isolation tests before the full suite.
4. Hygiene: remove reproducible caches only; preserve market data, research
   history, migrations, dependencies and existing work. Repair `make clean`,
   ignore transient outputs and update the visual contract.
5. Verify type checks, lint, unit tests, production build and browser flows.

## Research sources and architectural decisions

Retrieved with Firecrawl on 2026-09-12; original responses are local ignored
research artifacts under `.firecrawl/`.

- [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents):
  incremental work, explicit progress artifacts and verified completion. Apply
  this to persistent research steps and the existing experiment/validation
  ledgers. A model response alone must not mark a research step complete.
- [DeerFlow](https://github.com/bytedance/deer-flow): progressively loaded
  skills and separated execution responsibilities. Borrow the boundaries;
  avoid importing another orchestration stack into this Celery application.
- [TradingAgents](https://github.com/TauricResearch/TradingAgents): distinct
  analyst and risk roles. Financial research benefits from explicit hypothesis,
  evidence and critique; model agreement is not a statistical validation gate.
- [OpenAI Codex](https://github.com/openai/codex): a local coding-agent precedent,
  also reviewed through Firecrawl. Its repository is not a financial research
  engine; this change does not embed Codex or require a second agent runtime.

The recommended Axiom flow is hypothesis → reproducible experiment → independent
validation → research note. UI presents actions; API validates and enqueues;
Worker executes and records results; Agent reads aggregate facts and proposes
allowed next steps; quant code owns calculations. Financial research provenance
must retain strategy version, snapshot and trial identity. External sources are
evidence, never runtime instructions or authorization.

Full autonomous planning, resumable multi-step runs and additional model
providers require separate contracts for budgets, cancellation, checkpoints
and evidence freshness. They are an architectural direction, not a capability
claimed by this interface change. The existing bounded assistant remains the
actual execution capability.

## Verification evidence and limits

The accepted screenshots are saved outside the repository in the Codex
visualizations folder (2026/09/12, task 01a09363-6924-7152-a163-82278185d9e6):
`axiom-strategies.png`, `axiom-overview.png`, `axiom-strategy-detail.png`.

Browser checks covered the strategy collection with real existing records,
no-match search and clearing, detail navigation, assistant open/close, secondary
navigation disclosure, and a 390px mobile viewport. The overview rendered its
existing equity series. Desktop and mobile document widths matched their
viewports. The local production preview uses port 3101 and the existing API
on port 8000. Backend changes were validated by unit tests; no remote deployment
or new model-driven experiment was performed by this work package.

The broad engine/broker end-to-end suite and Docker golden backtest were not
rerun: this package changes presentation and read-only Agent aggregation, not
quant calculations or execution. The provider remains configured by the
existing runtime; the new UI does not claim autonomous financial research.

`make clean` was executed before the first production build. It removes only
reproducible build/test caches; Python dependencies and research data survive.
A test-only settings fixture now excludes local dotenv files and resets cached
settings, so the test process cannot accidentally load a local model key.
