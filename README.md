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
| [`docs/PHASE-1.5.md`](docs/PHASE-1.5.md) | Phase 1.5 可信性加固（已完成） |
| [`docs/PHASE-2.md`](docs/PHASE-2.md) | **当前阶段**的可执行任务清单（WP-1 → WP-4） |
| [`docs/architecture.md`](docs/architecture.md) | 目标架构、不可违反的边界、可复现性契约 |
| [`docs/data-sources.md`](docs/data-sources.md) | 数据源与摄取 |
| [`design-system/axiom-quant/MASTER.md`](design-system/axiom-quant/MASTER.md) | 设计令牌与反模式 |
| [`.cursor/rules/axiom-quant.mdc`](.cursor/rules/axiom-quant.mdc) | 施工纪律（自动注入，每个 PR 都受约束） |

## 当前状态

**Phase 0 + Phase 1 + Phase 1.5 已完成**：SPY 200DMA 经 LEAN Docker 产出真实订单；指标由 Axiom 自算；数据快照不可变；回测走 Celery；取消会杀掉容器。

**Phase 2 进行中 — 数据平台化。** 摄取与引擎已按 `symbols` 参数化。标的池时点正确、Polygon 对账、增量摄取尚未交付。在此之前不要把回测数字用于真实投资决策。

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

### 摄取行情

```bash
python -m quant.data.ingest_spy SPY
python -m quant.data.ingest_spy SPY QQQ
# 或 POST /api/v1/data/ingest
# 或在 Settings 填写标的后点「拉取行情」
```

### 测试

```bash
pytest tests/unit -q
pytest -m golden        # 需要 Docker + LEAN 镜像
```

## 许可

- LEAN: Apache-2.0
- TradingView Lightweight Charts: Apache-2.0（须保留 attribution，见 `NOTICE`）
