<p align="center">
  <img src="brand/logo.png" alt="Axiom Street" width="160" />
</p>

<h1 align="center">Axiom Street</h1>

<p align="center">
  <strong>Honest quantitative research.</strong><br />
  Built so you cannot easily fool yourself.
</p>

<p align="center">
  A research workbench where statistical validity is a first-class product feature —<br />
  not an optional appendix at the bottom of a pretty backtest report.
</p>

---

## Why Axiom Street exists

The real failure mode in quant research is not “failing to find a strategy.”  
It is **finding a strategy that never existed — and believing it**.

Any competent programmer can surface a Sharpe 2.5 equity curve on SPY in an afternoon.  
That curve is usually fake. Not because the data is wrong, and not because the code has a bug —  
but because **you tried four hundred variants on the same sample and kept the best one**.

Most platforms optimize for faster, prettier backtests.  
Axiom Street optimizes for a different outcome: **numbers you are allowed to trust**.

> Full product constitution: [`docs/VISION.md`](docs/VISION.md)

---

## Principles that ship in the product

| Principle | What it means in practice |
|-----------|---------------------------|
| **Fail loud** | Missing corporate actions fail the backtest. Silent fallbacks are bugs. |
| **Metrics belong to Axiom** | We compute Sharpe / drawdown / etc. from the return series. LEAN stats are cross-checks only. |
| **Immutable data** | Snapshots are content-addressed. Ingest never overwrites history. |
| **Trial ledger** | Every backtest is counted. Multiple-testing penalties cannot be reconstructed after the fact. |
| **Validation before AI** | Phase 3 ships before Copilot. Without validation, AI is an overfitting amplifier. |

---

## Architecture at a glance

```
apps/web          Next.js research UI
services/api      FastAPI — sole database write path
services/worker   Celery — owns docker.sock, runs LEAN
quant/            Pure Python quant core (engine · data · metrics · risk)
data/             Immutable market snapshots + manifests
docs/             Vision · roadmap · architecture · data contracts
design-system/    Design tokens (restraint over spectacle)
brand/            Official mark
```

Hard boundaries (non-negotiable):

- Controllers never call LEAN internals — only `QuantEngine`
- Strategies never know about brokers
- Risk cannot be bypassed by strategy code or AI
- Backtests run in workers, never in the API process

Details: [`docs/architecture.md`](docs/architecture.md)

---

## Stack

| Layer | Choice |
|-------|--------|
| Web | Next.js · TypeScript · Tailwind · Monaco · Lightweight Charts |
| API | FastAPI · SQLAlchemy · Alembic · PostgreSQL |
| Jobs | Celery · Redis · SSE |
| Quant | LEAN (Docker, pinned) · pandas · DuckDB · Parquet |
| Infra | Docker Compose |

Mature components over vanity engineering. We do not rewrite a backtester for sport.

---

## Current status

| Phase | Status |
|-------|--------|
| 0–1 Foundation + SPY 200DMA path | Done |
| 1.5 Trust hardening (fail-loud, Celery, trial ledger) | Done |
| **2 Data platform** (PIT universes ✓, incremental ingest ✓, dual-source scaffold ✓) | **In progress** |
| 3 Validation engine | Next |
| 4–8 Research · AI · Paper · Live · Portfolio | Sequenced after validation |

Do not treat backtest numbers as investment advice until Phase 2–3 close the remaining trust gaps.

Roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md)

---

## Quick start

```bash
# Requires Docker Desktop
docker compose up --build
```

| Surface | URL |
|---------|-----|
| Web | http://localhost:3000 |
| API health | http://localhost:8000/health |
| OpenAPI | http://localhost:8000/docs |

### API only

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn services.api.main:app --reload --port 8000
```

### Ingest market data

```bash
python -m quant.data.ingest_spy SPY
python -m quant.data.ingest_spy SPY QQQ --mode incremental
```

Configuration uses the `STREET_` env prefix (see `.env.example`).

### Tests

```bash
pytest tests/unit -q
pytest -m golden        # requires Docker + pinned LEAN image
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| [`docs/VISION.md`](docs/VISION.md) | What we are — and what we refuse to become |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Phased construction blueprint |
| [`docs/architecture.md`](docs/architecture.md) | Layers, boundaries, reproducibility contract |
| [`docs/data-sources.md`](docs/data-sources.md) | Providers, capabilities, ingest layout |
| [`design-system/axiom-street/MASTER.md`](design-system/axiom-street/MASTER.md) | Tokens and anti-patterns |
| [`.cursor/rules/axiom-street.mdc`](.cursor/rules/axiom-street.mdc) | Engineering discipline for every PR |

---

## License & attribution

- QuantConnect LEAN — Apache-2.0
- TradingView Lightweight Charts — Apache-2.0 (attribution required; see [`NOTICE`](NOTICE))

---

<p align="center">
  <sub>Axiom Street — research discipline, productized.</sub>
</p>
