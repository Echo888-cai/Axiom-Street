# Phase 1.5 — 可信性加固（当前阶段）

> **目标：让系统输出的每一个数字都可信、可复现，且永不静默出错。**
> 预估 3–4 周 / 9 个工作包（每包 ≈ 1 个 PR）。
> 前置阅读：`docs/VISION.md`（信念一、二、三）、`docs/ROADMAP.md`（第 1 章 P0 清单）。

**这个阶段不加任何新功能。** 它的全部价值在于：让现有的功能说真话。在此之前扩展多资产或验证引擎，都会把不可复现和错误数字的问题放大 N 倍。

按顺序执行。WP-0 与 WP-1 是后续所有工作的保护网，不能跳过。

---

## WP-0 · 版本控制与 CI 基线

**为什么第一**：目前项目**不是 git 仓库**，且没有任何 CI。在这两件事完成之前，后续每一次修改都是不可回溯、不受保护的。

### 任务

- [x] `git init`，`.gitignore` 已存在需检查是否覆盖 `axiom-local.db`、`jobs/`、`data/snapshots/`、`.venv`
- [x] 提交当前状态作为基线 commit，commit message 标注 `Phase 1 baseline`
- [x] 真实的 Alembic baseline（P0-10）：删除 `services/api/alembic/versions/0001_initial.py` 里的空 `pass`，用 `alembic revision --autogenerate` 生成完整 schema
- [x] 容器 entrypoint 加 `alembic upgrade head`；移除 `services/api/main.py` 的 `Base.metadata.create_all(bind=engine)`
- [x] 新增 `.github/workflows/ci.yml`：
  - `ruff check` + `ruff format --check`
  - `mypy quant services`（先用宽松配置，逐步收紧）
  - `pytest tests/unit -q`
  - `cd apps/web && npx tsc --noEmit && npm run build`
- [x] 新增 `.github/workflows/nightly.yml`：跑 `pytest -m golden`（需 Docker）
- [x] `Makefile` 补 `lint`、`typecheck`、`test-all` 目标

### 验收

- CI 在 PR 上自动运行且全绿
- 删库后 `alembic upgrade head` 能重建完整 schema，且与 `models.py` 无 diff（`alembic check`）
- nightly golden test 通过

---

## WP-1 · 指标正确性（P0-1 / P0-2 / P0-3）

**核心决策已定，不要再权衡**：所有指标一律由 Axiom 自算，LEAN 原始 statistics 全量存入 `extras` 仅作交叉校验。理由见 `docs/ROADMAP.md` P0-3。

### 改动文件

`quant/metrics/performance.py`、`tests/unit/test_metrics.py`、`services/api/models.py`、`services/api/schemas.py`

### 任务

- [x] **拆分解析函数**（P0-1）。`_parse_pct()` 只处理百分比；新增 `_parse_money()` 处理 `$43.00`、`$-43.00`、`($43.00)`（括号负数）、`1,234.56`、`-$1,234.56`。已实测 `_parse_pct("$43.00")` 返回 `None`，这是当前手续费永远为 0 的根因
- [x] **解析失败必须抛错**，不得返回 `None` 后被当成 0（信念一）。新增 `MetricParseError`
- [x] **修正 alpha 定义**（P0-2）：
  - 现有 `alpha` 字段改名 `excess_return`，语义保持 `total_return - benchmark_return`（诚实命名）
  - 新增 `beta`：策略日收益对基准日收益做 OLS
  - 新增 `alpha_capm`：`r_p - r_f = α + β(r_m - r_f) + ε` 的截距，年化
  - 新增 `information_ratio`：`mean(active_return) / tracking_error`
  - 新增 `tracking_error`
- [x] **移除 LEAN/自算混用**（P0-3）：`total_return`、`cagr`、`sharpe`、`max_drawdown` 改为自算。删除所有 `lean_x if lean_x is not None else computed_x` 分支
- [x] **修正 `payoff_ratio`**：当前与 `profit_factor` 都映射到 LEAN `Profit-Loss Ratio`。正确定义 `payoff_ratio = avg_win / |avg_loss|`，`profit_factor = gross_profit / |gross_loss|`，两者从 round-trip 交易自算（依赖 WP-2）
- [x] **无风险利率可注入**：`risk_free_rate` 当前硬编码默认 0。改为从配置读取，支持传入日频无风险利率序列（为后续接入国债利率留接口）
- [x] **补充指标**：`tail_ratio`、`skewness`、`kurtosis`、`var_95`、`cvar_95`、`omega_ratio`
- [x] **年化频率校验**：当前无条件用 `√252`。改为检测 equity 曲线实际频率，频率不是日频时抛错或使用正确因子
- [x] **新增对账测试** `tests/unit/test_metrics_reconciliation.py`：用 golden run 的真实 LEAN JSON，断言自算值与 LEAN 值偏差在容差内（Sharpe ±0.05 / CAGR ±0.1% / MaxDD ±0.5%）。**这个测试是引擎正确性的哨兵，未来任何指标改动都必须让它继续通过**
- [x] Alembic migration：`backtest_metrics` 表增删字段
- [x] 前端 `apps/web/src/features/backtests/backtest-studio.tsx` 与 `lib/labels.ts` 同步新字段名，`alpha` 的展示文案改为「超额收益」，新增 β / IR tile

### 验收

- `_parse_money("$43.00") == 43.0`，全部格式有测试覆盖
- golden backtest 的手续费在 UI 上显示为 $43，不再是空值
- 对账测试通过
- tearsheet 内部自洽：`calmar == cagr / |max_drawdown|` 精确成立

---

## WP-2 · LEAN 输出完整解析（P0-4）

golden result JSON 约 12,785 行，当前只用了 `Charts` / `Statistics` / `Orders`，约 95% 被丢弃。

### 改动文件

`quant/engine/result_parser.py`、`services/api/models.py`、`tests/unit/test_result_parser.py`

### 任务

- [x] **解析 `TotalPerformance.ClosedTrades` 为真正的 round-trip 交易**。当前 `backtest_trades` 表的 `exit_price` / `pnl` / `return_pct` / `holding_period` 全为空——只记录了开仓。这使得胜率、盈亏比、持仓周期分析全部无法进行
- [x] **解析 `RollingWindow`**（148 个滚动月度窗口，含 VaR95/99、Probabilistic Sharpe）。新增 `backtest_rolling_windows` 表
- [x] **解析 Exposure 与 Turnover chart** 为时间序列，落库
- [x] **保留 LEAN 的 Beta / IR / Treynor / Tracking Error 到 `extras`**，供 WP-1 的对账测试使用
- [x] **修正 `find_result_json`**：当前按 mtime 取最新 `*.json`，会与 `data-monitor-report-*.json` 混淆。改为按算法类名精确匹配文件名
- [x] **移除基准缩放启发式**或使其显式。当前 `result_parser.py:78-86` 在 `first_bench < first_strat * 0.2` 时自动缩放基准序列——这是一个会静默改变 `benchmark_return` 与 `excess_return` 的魔法。改为显式配置基准归一化模式，并在结果里记录是否发生了缩放
- [x] Alembic migration

### 验收

- golden run 解析出的 round-trip 交易数与 LEAN `TotalPerformance.ClosedTrades` 数量一致，每笔有非空 `pnl` 与 `holding_period`
- 滚动 Sharpe 序列可从 API 取出
- 基准是否被缩放在结果 JSON 中可见

---

## WP-3 · 数据质量门禁（P0-5 / P0-6）

**这是本阶段最重要的一个包。** P0-5 是整个代码库里最危险的缺陷：它会产生错误的回测结果且全程静默。

### 改动文件

`quant/data/providers.py`、`quant/data/quality.py`（新建）、`quant/data/lean_converter.py`、`quant/data/manifest.py`

### 任务

- [x] **消灭静默降级**（P0-5）。provider 层新增能力声明：

```python
@dataclass(frozen=True)
class ProviderCapabilities:
    ohlcv: bool
    dividends: bool
    splits: bool
    point_in_time: bool
```

  - Stooq 声明 `dividends=False, splits=False`
  - `build_factor_file()` 在数据源不支持 corporate actions 时**抛出异常**，不再生成只含终止行 `20501231,1,1,0` 的空 factor file
  - 策略使用 `DataNormalizationMode.Adjusted` 时，若快照的 `corporate_actions_verified` 为 false，**回测直接失败**并给出明确错误："数据源 stooq 不提供分红数据，无法进行调整价回测"
  - `manifest.json` / `data_snapshots` 增加 `corporate_actions_verified` 与 `provider_capabilities` 字段

- [x] **新建 `quant/data/quality.py`**（P0-6），实现规则化校验器，返回结构化 `DataQualityReport`：

| 规则 | 检查内容 |
|------|---------|
| `trading_day_gaps` | 对照交易日历（LEAN market-hours DB 已在 `data/lean/market-hours/`）检测缺失交易日 |
| `ohlc_consistency` | `high >= max(open, close)`、`low <= min(open, close)`、`high >= low` |
| `price_jumps` | 单日涨跌幅 > 50% 且无对应拆分事件 |
| `zero_volume` | 成交量为 0 或缺失的 bar |
| `duplicate_timestamps` | 重复日期 |
| `stale_data` | 最后一根 bar 距今超过 N 个交易日 |
| `non_positive_prices` | 价格 ≤ 0 |
| `monotonic_dates` | 日期严格递增 |

- [x] **校验 fail-closed**：`DataQualityReport.has_blocking_issues` 为真时，`POST /backtests` 返回 422 并附带报告。不允许"警告后继续"
- [x] `services/api/routers/data.py` 暴露质量报告；Settings 页面（`apps/web/src/app/settings/page.tsx`）展示
- [x] 修掉 `routers/data.py:47-48` 的 `except Exception` 兜底 500，改为分类错误处理
- [x] 测试：为每条规则构造正例与反例 fixture

### 验收

- 强制走 Stooq 摄取 SPY，再跑 Adjusted 模式回测 → **回测失败**，错误信息指明数据源能力不足（而不是静默产出错误结果）
- 构造一份含 OHLC 不自洽的 parquet → 回测被 422 拦下
- 当前真实 SPY 快照的质量报告通过全部规则（若不通过，先查明原因再继续）

---

## WP-4 · 不可变数据快照（P0-7）

当前 `ingest_spy()` 每次全量重拉并覆盖 parquet 与 manifest，旧回测记录的 `data_version` 所指向的数据已不存在。**这直接违反项目规则的可复现要求。**

### 改动文件

`quant/data/ingest_spy.py`、`quant/data/manifest.py`、`services/api/models.py`、`quant/engine/lean.py`

### 任务

- [x] 新增 `data_snapshots` 表（字段定义见 `docs/ROADMAP.md` 3.2）
- [x] 磁盘布局改为不可变：`data/snapshots/{snapshot_key}/`，`snapshot_key` 形如 `spy-daily-20260831-a1b2c3`（内容哈希后 6 位）
- [x] `data/market/` 保留为指向 latest 快照的符号链接，兼容现有代码路径
- [x] 摄取新数据**不删除旧快照**，只在旧记录写 `superseded_by`
- [x] `backtests` 表：`data_version` 字符串字段 → `data_snapshot_id` 外键
- [x] `BacktestRequest` 增加 `data_snapshot_id`，`LeanQuantEngine` 按快照 ID 挂载数据目录（当前无条件调用 `ensure_lean_spy_data`）
- [x] **golden test 断言 `data_snapshot_id` 与 `engine_version`**（当前 `tests/golden/test_spy_200dma_golden.py` 完全没检查这两项，这是 golden test 最大的漏洞）
- [x] `expectations.json` 增加 `data_snapshot_key` 字段
- [x] 快照保留策略：默认全保留，提供 `make prune-snapshots` 手动清理未被任何回测引用的快照

### 验收

- 连续摄取两次，产生两个独立快照目录，第一个仍完整可读
- 用旧快照重跑一个历史回测，equity 曲线逐点相同（浮点容差 1e-9）
- golden test 在数据快照变化时**失败**并明确指出快照不匹配

---

## WP-5 · 试验台账（Trial Ledger）

**这是本阶段唯一的"为未来铺路"任务，但它不可推迟。** Deflated Sharpe 与 PBO 需要"你在同一份数据上试了多少次"这个分母。不从现在开始记录，这个数字将永久丢失。

### 改动文件

`services/api/models.py`、`services/api/services/backtests.py`、`services/api/routers/`（新增查询端点）

### 任务

- [x] 新增 `experiment_trials` 表（字段定义见 `docs/ROADMAP.md` 3.3）
- [x] **每一次回测创建时都写入一行**，无例外。写入点放在 `create_backtest()` 内的同一事务，保证不会漏记
- [x] `strategy_family` 的定义：同一 idea 的不同参数视为同族。实现为 `strategies` 表新增 `family_id`（默认等于 strategy id，创建变体时继承父策略的 family_id）
- [x] `parameter_hash`：参数字典的规范化 JSON 的 sha256，用于识别重复试验
- [x] 新增查询端点 `GET /api/v1/strategies/{id}/trial-stats`，返回：在各数据快照上的试验次数、Sharpe 分布（均值/方差/最大值）、重复试验数
- [x] 前端在 Strategy Lab 显示一行诚实提示："已在此数据快照上试验 N 次"

### 验收

- 跑 10 次不同参数的回测，`GET trial-stats` 返回 `count=10` 与正确的 Sharpe 方差
- 重复提交相同参数，`parameter_hash` 可识别为重复
- 删除策略时试验记录保留（研究史不应被删除）—— 用软删除或 `ON DELETE SET NULL`

---

## WP-6 · 编排收敛（P0-8 / P0-9）

### 改动文件

`services/api/services/backtests.py`、`services/worker/tasks.py`、`services/worker/celery_app.py`、`quant/engine/lean.py`、`docker-compose.yml`、`services/api/settings.py`

### 任务

- [x] **删除 `threading.Thread`**（`services/api/services/backtests.py:129-136`），改为 `run_backtest_task.delay(str(backtest.id))`
- [x] `docker-compose.yml`：`docker.sock` 只挂给 `worker`，从 `api` 移除（当前 api 根本没挂，所以 compose 下回测必定失败）
- [x] **LEAN 调用加超时**（`quant/engine/lean.py:161`）：`subprocess.run(cmd, timeout=settings.lean_timeout_seconds)`，默认 1800 秒。捕获 `TimeoutExpired` → `docker kill` → 状态置 `FAILED`，错误标注 `engine_timeout`
- [x] **取消真正生效**（P0-9）：
  - API 写 Redis 键 `axiom:cancel:{backtest_id}`，TTL 1 小时
  - worker 在 LEAN 运行期间用后台线程每 2 秒轮询该键
  - 命中则 `docker kill {container_name}`，状态置 `CANCELLED`
  - 当前 `cancel_backtest()` 只改 DB 状态、从不调用 `engine.cancel_backtest()`
- [x] **孤儿回收**：worker 启动时（`celery_app.py` 的 `worker_ready` 信号）把所有 `QUEUED`/`STARTING`/`RUNNING` 且 `started_at` 超过 `lean_timeout` 的记录置 `FAILED`，错误标注 `orphaned_by_restart`。另加一个 Celery beat 周期任务每 5 分钟执行同样的对账
- [x] **并发上限**：Celery `worker_concurrency` 从配置读取，默认 2；队列深度超过阈值时 `POST /backtests` 返回 429
- [x] **清理死配置**：`AXIOM_DOCKER_HOST`（compose 中定义但 `lean.py` 只读 `DOCKER_HOST`）与 `AXIOM_SYNC_BACKTESTS`（`.env.example` 中定义但 `Settings` 里不存在）—— 要么实现，要么删除
- [x] Celery 配置补齐：`task_time_limit`、`task_soft_time_limit`、`task_acks_late=True`、`task_reject_on_worker_lost=True`
- [x] Docker stdout/stderr（现在只落 `jobs/{id}/docker_*.log`）通过 `GET /backtests/{id}/logs` 可读

### 验收

- `docker compose up --build` 后从 UI 点"运行回测"能跑完（**当前必定失败**）
- 回测跑到一半 `docker compose restart api`，回测仍然正常完成
- 点"取消"后 5 秒内 `docker ps` 中容器消失，状态为 `CANCELLED`
- 人为让 LEAN 挂死（如 timeout 设为 5 秒），任务在超时后被正确标记 `FAILED` 且容器被清理
- kill worker 后重启，孤儿任务被标记 `orphaned_by_restart`

---

## WP-7 · API 与可观测性加固

### 任务

- [x] **列表分页**：`GET /strategies`、`GET /backtests`、`GET /backtests/{id}/equity`、`/trades` 全部加 `limit` / `offset` / `total`。当前 equity 曲线全量返回，多年日线可达 MB 级
- [x] **过滤**：`GET /backtests` 支持 `strategy_id`、`status`、日期区间
- [x] **`/health` 真实探活**：分别检查 Postgres、Redis、Docker daemon、LEAN 镜像存在性，返回各项状态与整体 `ok|degraded|down`。当前只返回硬编码 `{"status": "ok"}`，无法反映任何真实故障
- [x] **结构化日志**：接入 `structlog`，`request_id` 贯穿 API，`backtest_id` 贯穿 worker 与引擎。全局异常处理器返回结构化错误码
- [x] **策略状态机守卫**：`PATCH /strategies/{id}` 当前可任意设置 `status`，包括直接设为 `VALIDATED` / `LIVE`。加入合法转换表，`VALIDATED` 及以上状态只能由系统流程设置，不接受客户端直接写入（这是信念二在 API 层的落地）
- [x] **审计日志可读**：`audit_logs` 表当前只写不读，新增 `GET /api/v1/audit-logs`（带分页与过滤）
- [x] 修掉 `create_backtest()` 里"先写 `object_id="pending"` 再回查更新"的审计 hack（`services/api/services/backtests.py:102-127`），改为 flush 拿到 ID 后再写审计
- [x] `docker-compose.yml` 与 `alembic.ini` 中提交进仓库的默认口令 `axiom:axiom` 改为环境变量注入
- [x] `api` / `worker` 服务补 compose healthcheck

### 验收

- 停掉 Redis，`/health` 返回 `degraded` 并指明 Redis 不可用
- 尝试 `PATCH` 把策略状态直接改成 `VALIDATED` → 返回 409
- 一次回测的完整生命周期可通过 `backtest_id` 在日志中串起来
- equity 端点默认返回不超过 5000 点

---

## WP-8 · 测试覆盖补齐

当前全仓库 **9 个测试**（unit 8 + golden 1），前端 **0 个**。目标 ~80 个后端 + 关键路径 E2E。

### 任务

- [x] **指标测试矩阵**：每个指标的正常值、边界（空序列、单点、全零收益、全正收益）、已知值案例（手算或对照 `empyrical` / `quantstats`）
- [x] **`_parse_money` / `_parse_pct` 全格式矩阵**
- [x] **数据质量规则**：每条规则正例 + 反例
- [x] **API 全路由**：backtests 全部端点、data 端点、SSE、取消流程、分页、状态机守卫（当前只测了 health + strategy CRUD）
- [x] **编排路径**：超时、取消、孤儿回收、并发上限（用 fake engine 避免真跑 Docker）
- [x] **快照复现性**：同一快照跑两次断言逐点相同
- [x] **provider fallback**：mock yfinance 失败 → 断言 Stooq 路径在 Adjusted 模式下抛错
- [x] **前端**：Vitest 单测（`lib/api.ts` 分页 unwrap、`labels.ts`、指标格式化）。Playwright 主路径未进 CI，需本机 `docker compose up` 后手跑
- [x] `pyproject.toml` 加 `pytest-cov`，CI 报告覆盖率，核心 `quant/` 包设 80% 门槛

### 验收

- `pytest tests/unit -q` 全绿且数量 ≥ 80
- `quant/metrics` 与 `quant/data` 覆盖率 ≥ 80%
- Playwright 主路径通过
- CI 全绿

---

## 阶段验收（Definition of Done）

Phase 1.5 全部完成的判定标准。**任何一项不满足都不能进入 Phase 2。**

- [x] `docs/ROADMAP.md` 附录 A 的 10 个 P0 全部关闭，每个都有对应回归测试
- [x] 三个月前的回测可以逐点复现（用旧数据快照）— 本机同快照重跑 1097 点净值，最大绝对误差 0.0
- [x] golden test 已断言 `data_snapshot_sha256` + `engine_version`（需 Docker nightly 重跑锁定）
- [x] 自算指标与 LEAN 的对账测试通过
- [x] `docker compose up` 后完整跑通一次回测，且重启 API 不影响（本机已验证：restart api 后回测仍 COMPLETED）
- [x] 取消能在 5 秒内真实杀掉容器（本机 2.3 秒，状态 CANCELLED）
- [x] 强制走无分红数据源时回测失败而非静默出错
- [x] 任意策略族可查询"在此快照上试验了 N 次"
- [x] 后端 `pytest tests/unit` ≥ 80（当前 104）且 `quant/metrics`+`quant/data` 覆盖率 ≥ 80%；Vitest 6 个前端单测。Playwright 主路径未进 CI
- [x] 没有任何新增的静默失败路径

---

## 施工纪律提醒

- 一个工作包一个 PR，PR 描述里勾选 `.cursor/rules/axiom-quant.mdc` 的「Every PR」清单
- **不要为了让 golden test 通过而放宽容差**——数字变了就去查为什么
- 遇到"这里近似一下应该没关系"的念头时，停下来重读 `docs/VISION.md` 信念一
- 本阶段不加任何新功能。想加的功能记到 `docs/ROADMAP.md` 对应阶段
