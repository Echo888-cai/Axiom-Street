# Axiom Street 架构

> 本文描述**目标架构**，并标注每一层的当前状态。
> 愿景见 `docs/VISION.md`，施工计划见 `docs/PLAN.md`，闸门规格见 `docs/validation-gates.md`。

## 仓库布局

| 路径 | 职责 |
|------|------|
| `apps/web` | Next.js 研究工作台 UI（**唯一产品前端**） |
| `services/api` | FastAPI；唯一的数据库写入路径 |
| `services/worker` | Celery worker；持有 `docker.sock`，执行 LEAN |
| `quant/` | 纯 Python 量化核心（不依赖 web framework） |
| `data/` | 不可变行情快照与 manifest |
| `tests/` | 单元测试 + Golden Backtest |
| `design-system/axiom-street` | 设计令牌 |
| `brand/` | 品牌主视觉 |
| `docs/` | 愿景 / 计划 / 架构 / 数据契约 / 闸门规格 |

---

## 当前前端实现（2026-09-05）

`apps/web/src/app` 负责路由；`features` 负责业务；`components` 负责通用外观；`lib/api` 按策略、回测、验证、数据、标的池、笔记和代码服务拆分。浏览器经 `/api/backend` 同源网关访问 FastAPI，`API_BASE_URL` 在 Next.js 服务端运行时读取。SSE 与下载均走同一链路。详细目录及运行约定见 [前端接手说明](frontend-handoff.md)。

## 1. 分层与边界

```
┌─────────────────────────────────────────────────────────────┐
│  Web (Next.js)                                              │
│  Strategy Lab · Tearsheet · Validation · Research notes      │
└───────────────────────────┬─────────────────────────────────┘
                            │  REST /api/v1  +  SSE
┌───────────────────────────▼─────────────────────────────────┐
│  API (FastAPI)                                              │
│  routers → services → models          ← 唯一的 DB 写入路径   │
└─────────┬─────────────────────────────────┬─────────────────┘
          │ Celery (Redis broker)           │
┌─────────▼───────────────┐     ┌───────────▼─────────────────┐
│  Worker (Celery)        │     │  PostgreSQL                 │
│  回测 · 验证 · 摄取      │     │  策略 · 回测 · 试验台账      │
└─────────┬───────────────┘     └─────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────┐
│  quant/  (纯 Python 库，不依赖 FastAPI / Celery)             │
│  engine · data · metrics · validation · risk · strategy_sdk  │
└─────────┬───────────────────────────────────────────────────┘
          │ docker run --network none
┌─────────▼───────────────────────────────────────────────────┐
│  LEAN (quantconnect/lean:pinned)  ← 唯一的回测执行者          │
└─────────────────────────────────────────────────────────────┘
```

### 不可违反的边界

| 边界 | 规则 | 违反的后果 |
|------|------|-----------|
| Controller ↛ LEAN | API 与 Controller 只能通过 `QuantEngine` ABC 访问引擎 | 换引擎需要重写整个 API 层 |
| Strategy ↛ Broker | 策略代码不知道 Alpaca / IBKR 的存在 | 策略与执行耦合，无法在回测/模拟/实盘间迁移 |
| Risk ⊥ everything | 风控引擎独立，不可被策略代码或 AI 绕过 | 单次错误可以清空账户 |
| API ↛ Docker | 只有 worker 持有 `docker.sock` | API 进程内起容器无法编排、重启即孤儿 |
| quant/ ↛ web framework | `quant/` 包不 import FastAPI / Celery | 无法在 notebook 或 CLI 中独立使用 |

**当前状态**：`API ↛ Docker` 已在 Phase 1.5 落地（Celery worker 持有 `docker.sock`）。`Risk ⊥ everything` 的风控引擎仍是未被引用的 stub，要到 Phase 6 才实体化。

---

## 2. 量化数据流

```
Vendor API (yfinance / Polygon / Stooq)
    │
    ├─ ProviderCapabilities 声明（能否提供分红/拆分/时点数据）
    ▼
_normalize()  →  DataQualityReport  ──不通过──▶  阻塞，回测失败
    │ 通过
    ▼
不可变快照  data/snapshots/{snapshot_key}/
    ├─ market/{symbol}.parquet          规范化 OHLCV
    ├─ corporate_actions/{symbol}.parquet
    └─ manifest.json                    sha256 · 能力声明 · 质量报告
    │
    ▼
LEAN 转换  data/snapshots/{key}/lean/
    ├─ equity/usa/daily/{symbol}.zip    deci-cents CSV
    ├─ factor_files/{symbol}.csv        分红/拆分累积因子
    └─ map_files/{symbol}.csv           时点正确的 ticker 映射
    │
    ▼
docker run --network none  -v snapshot/lean:/Data:ro
    │
    ▼
Spy200DmaAlgorithm.json  (12,785 行)
    │
    ├─ Charts          → equity / benchmark / drawdown / exposure / turnover
    ├─ Statistics      → 存入 extras，仅作对账
    ├─ Orders          → 订单事件
    ├─ TotalPerformance→ round-trip 交易（含 pnl / holding_period）
    └─ RollingWindow   → 148 个滚动窗口（VaR · Probabilistic Sharpe）
    │
    ▼
Axiom 自算全部指标（LEAN 值仅用于对账测试）
    │
    ▼
PostgreSQL：metrics · equity · trades · monthly_returns · rolling_windows
          + experiment_trials（多重检验的分母）
```

### 关键不变量

1. **快照不可变**。摄取新数据写新快照，旧快照只标记 `superseded_by`，永不覆盖。
2. **每个回测记录 `data_snapshot_id` + `engine_version`**。二者相同则结果必须逐点相同。
3. **每个回测写一行 `experiment_trials`**。这是 Deflated Sharpe 与 PBO 的分母，无法事后重建。
4. **指标一律自算**。LEAN 的 statistics 只进 `extras`，由对账测试守卫两者一致。
5. **失败优于近似**。数据源能力不足、质量校验不通过、解析失败——全部抛错，不降级。

---

## 3. 数据模型

### 已实现（Phase 1）

| 表 | 用途 |
|----|------|
| `users` | 存在但**完全孤立**：无任何表引用它，`created_by` 是硬编码 `"local"` |
| `strategies` | 策略元数据 + 生命周期状态 |
| `strategy_versions` | 版本化的策略代码 + 配置（`(strategy_id, version)` 唯一） |
| `backtests` | 回测运行记录 + 引擎/数据版本 |
| `backtest_metrics` | 1:1 指标（30+ 字段 + `extras` JSON） |
| `backtest_equity` | 净值时间序列 |
| `backtest_trades` | 交易记录（当前只有开仓，`pnl`/`exit_price` 全空） |
| `backtest_monthly_returns` | 月度收益 |
| `audit_logs` | 变更审计（当前只写不读，actor 永远是 `"local"`） |

### Phase 1.5 新增

| 表 | 用途 | 为什么必要 |
|----|------|-----------|
| `data_snapshots` | 不可变数据快照 + 血缘链 | 可复现性的唯一实现方式 |
| `experiment_trials` | 每次回测的试验记录 | DSR / PBO 的分母，**不可事后补算** |
| `backtest_rolling_windows` | 滚动窗口指标 | 滚动 Sharpe / VaR，来自被丢弃的 LEAN 输出 |

### Phase 2 新增

`universes` + `universe_members`（含 `effective_from` / `effective_to`，消除生存者偏差）

### Phase 3 新增

`validation_runs`（walk-forward / DSR / PBO / 敏感性 / 成本 / bootstrap / regime / SPA 的运行与结论）

### Phase 6–7 新增

`orders` · `positions` · `fills` · `risk_limits` · `reconciliations`（回测–实盘对账，见 `docs/VISION.md` 北极星指标）

### Phase 8 新增

`portfolios` · `portfolio_allocations` · `factor_exposures`

---

## 4. 状态机

### 策略生命周期

```
DRAFT ──回测完成──▶ BACKTESTED ──验证通过──▶ VALIDATED
                                                │
                                          人工确认
                                                ▼
                        ARCHIVED ◀── PAUSED ◀── LIVE ◀── APPROVED ◀── PAPER
```

**守卫规则**（信念二在 API 层的落地）：

- `VALIDATED` **只能**由验证流水线的实际结果设置，客户端不可直接写入
- `LIVE` 需要人工显式确认 + 风控配置就绪
- `PATCH /strategies/{id}` 必须校验转换合法性

**当前状态**：`PATCH /strategies/{id}` 已有合法转换表；`VALIDATED` 及以上不能由客户端直接写入。真正把策略推入 `VALIDATED` 的验证流水线属于 Phase 3。

### 回测生命周期

```
QUEUED ─▶ STARTING ─▶ RUNNING ─▶ COMPLETED
   │          │          │
   └──────────┴──────────┴──▶ FAILED / CANCELLED
```

`FAILED` 的 `error` JSON 需带分类：`data_quality` · `engine_timeout` · `engine_error` · `orphaned_by_restart` · `provider_capability`。

---

## 5. 技术选型与理由

| 层 | 选择 | 理由 |
|----|------|------|
| 回测引擎 | **LEAN**（Docker，版本固定） | 经实战检验，自研引擎是虚荣工程 |
| 编辑器 | **Monaco** | VS Code 同源，Python 生态成熟 |
| 图表 | **Lightweight Charts** | 金融图表专用，性能好，Apache-2.0（需保留 attribution） |
| 主库 | **PostgreSQL** | 事务性元数据 + JSON 字段的平衡 |
| 分析查询 | **Parquet + pandas** | 零运维，Phase 8 若需列式扫描再引入 DuckDB |
| 队列 | **Celery + Redis** | 成熟，支持 beat / group / chord（参数扫描需要） |
| API | **FastAPI + SQLAlchemy + Alembic** | 类型化、OpenAPI 自动生成（可供前端 codegen） |
| 前端 | **Next.js + TypeScript + Tailwind** | 约定清晰，无自研设计系统的负担 |

**选型原则**：优先成熟组件。每一个自研决策都要回答"为什么现有方案不够"。

---

## 6. 可复现性契约

这是产品最核心的技术承诺，也是 golden backtest 存在的意义。

**契约**：给定相同的 `(strategy_code_hash, data_snapshot_id, engine_version, date_range, parameters)`，回测结果必须逐点相同。

**实现手段**：

- LEAN 镜像 tag 固定（`quantconnect/lean:16355`），不使用 `latest`
- 容器 `--network none`，杜绝运行时拉取外部数据
- 数据快照内容寻址且不可变
- `tests/golden/` 作为哨兵：跑两次断言 `final_equity` 一致（1e-6），并断言快照与引擎版本匹配预期

**当前状态**：golden test 断言快照指纹与引擎版本；ingest 写入不可变 `data/snapshots/{key}/`。Phase 2 要把这套契约从单标的 SPY 推广到任意 universe。

---

## 7. 安全模型

用户提交的**任意 Python 代码**会在 LEAN 容器内执行。这是产品的核心攻击面。

**部署模型（D2：单人自用、永不暴露）**

- API 与 Web 只绑 `127.0.0.1`，**不绑 `0.0.0.0`**
- `POST /api/v1/data/ingest` 是无认证的网络+磁盘 DoS 入口，**已知且接受的风险**，前提是它不可从外部到达
- `users` 表、`created_by="local"`、`audit_logs.actor="local"` 为**已知空壳**，不假装有意义
- 一旦有第二个人使用，认证与 `user_id` 贯穿立刻升级为 P0，插在当期工作包之后

**现有隔离**：`--network none` · `--memory 2g` · `--cpus 2` · `--pids-limit 256` · 数据目录只读挂载。

**待补**（Phase 6 之前）：seccomp profile · 只读根文件系统 · 非 root 用户 · 危险 import 的静态检查
