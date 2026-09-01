# Axiom Quant

**一个让你难以自欺的量化研究环境。**

量化研究真正的失败模式不是「找不到策略」，而是「找到了一个不存在的策略并且信了它」。Axiom Quant 不追求成为最快的回测器，而是成为最诚实的那个——把统计有效性当作核心功能，而不是可选的附加报告。

完整定位、核心信念与反目标见 **[`docs/VISION.md`](docs/VISION.md)**。

## 文档

按此顺序阅读：

| 文档 | 内容 |
|------|------|
| [`docs/VISION.md`](docs/VISION.md) | 产品愿景与六条核心信念。**与路线图冲突时以愿景为准** |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | 代码审查结论、P0 缺陷清单、全阶段施工蓝图 |
| [`docs/PHASE-1.5.md`](docs/PHASE-1.5.md) | **当前阶段**的可执行任务清单（WP-0 → WP-8） |
| [`docs/architecture.md`](docs/architecture.md) | 目标架构、不可违反的边界、可复现性契约 |
| [`docs/data-sources.md`](docs/data-sources.md) | 数据源与摄取 |
| [`design-system/axiom-quant/MASTER.md`](design-system/axiom-quant/MASTER.md) | 设计令牌与反模式 |
| [`.cursor/rules/axiom-quant.mdc`](.cursor/rules/axiom-quant.mdc) | 施工纪律（自动注入，每个 PR 都受约束） |

## 当前状态

**Phase 0 + Phase 1 已完成**：SPY 200DMA 策略通过 LEAN Docker 产生真实订单与成交，输出净值/回撤/月度收益，并由 golden backtest 锁定复现性。

**Phase 1.5 进行中 — 可信性加固**。诚实地说明当前的已知问题（详见 `docs/ROADMAP.md` 附录 A）：

- 手续费因解析缺陷永远显示为 0
- `alpha` 字段实为超额收益，缺 β 与 information ratio
- 数据源降级到 Stooq 时会静默产生未调整价格的错误回测
- 无数据质量校验；摄取会覆盖旧数据，历史回测暂不可复现
- 回测由 API 进程内的线程执行而非 Celery，`docker compose` 下点击回测会失败
- 取消功能只改数据库状态，不会真正终止 LEAN 容器
- 无认证、无 CI、9 个测试

这些在 Phase 1.5 全部关闭后才会进入 Phase 2。**在此期间，请不要把本项目的回测数字用于真实投资决策。**

## 技术栈

| 层 | 选择 |
|----|------|
| Web | Next.js · TypeScript · Tailwind · Monaco · Lightweight Charts |
| API | FastAPI · SQLAlchemy · Alembic · PostgreSQL |
| Jobs | Celery · Redis · SSE |
| Quant | LEAN (Docker, 版本固定) · pandas · DuckDB · Parquet |
| Infra | Docker Compose |

选型理由见 `docs/architecture.md` 第 5 节。原则是优先成熟组件——自研回测引擎是虚荣工程。

## 快速开始

```bash
# 需要 Docker Desktop
docker compose up --build
```

- Web: http://localhost:3000
- API: http://localhost:8000/health
- API 文档: http://localhost:8000/docs

### 仅启动 API（不起全栈）

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn services.api.main:app --reload --port 8000
```

### 摄取 SPY 数据

```bash
python -m quant.data.ingest_spy
# 或 POST /api/v1/data/ingest/spy
# 或在 Settings 页面点击「摄取 SPY」
```

### 测试

```bash
pytest tests/unit -q
pytest -m golden        # 需要 Docker + LEAN 镜像
```

## 许可

- LEAN: Apache-2.0
- TradingView Lightweight Charts: Apache-2.0（须保留 attribution，见 `NOTICE`）
