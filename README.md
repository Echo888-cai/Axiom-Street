<p align="center">
  <img src="apps/web/public/axiom-mark.svg" alt="Axiom Street" width="96" />
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

## White Studio · 浅色研究工作室

前端已整理为浅色设计系统与按业务划分的模块。启动、目录职责、同源 API 网关与已验证范围见 [前端接手文档](docs/frontend-handoff.md)，视觉规范见 [White Studio](design-system/axiom-street/MASTER.md)。

```sh
make up           # 完整 Docker 研究环境
make web          # 本地 Next.js 前端
make api          # 本地 FastAPI，优先使用 .venv
```

浏览器默认使用同源 `/api/backend`；Next.js 通过运行时 `API_BASE_URL` 连接后端。

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
| **当前阶段：Phase 4 研究工作台收尾** | 详见 [`docs/PLAN.md`](docs/PLAN.md) |

Do not treat backtest numbers as investment advice until Phase 4 closes.

### Deployment constraints (single-user, no auth)

> **This product is single-user and not exposed to any network.**
>
> - API and Web bind **only `127.0.0.1`**, never `0.0.0.0`
> - `POST /api/v1/data/ingest` is an unauthenticated network+disk DoS vector — **accepted risk** because it is unreachable from outside
> - `users` table, `created_by="local"`, `audit_logs.actor="local"` are **known empty shells**, not pretend-auth

If a second user ever appears, auth + `user_id` threading become P0 immediately.

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
python -m quant.data.ingest.cli SPY
python -m quant.data.ingest.cli SPY QQQ --mode incremental
python -m quant.data.ingest.cli --symbols-file tickers.txt
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
| [`docs/PLAN.md`](docs/PLAN.md) | **Single execution plan** (replaces ROADMAP.md) |
| [`docs/validation-gates.md`](docs/validation-gates.md) | 8 validation gate thresholds (only written record) |
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
