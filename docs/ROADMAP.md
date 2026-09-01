# Axiom Quant — 成长为顶级量化研究产品的路线图

> 本文档是施工蓝图。审查基准：2026-08-31，代码状态 = Phase 0 + Phase 1 已完成。
>
> **文档体系**
> - `docs/VISION.md` — 产品愿景与核心信念（**冲突时以愿景为准**）
> - `docs/ROADMAP.md` — 本文，全阶段施工蓝图
> - `docs/PHASE-1.5.md` — 当前阶段的可执行任务清单
> - `docs/architecture.md` — 目标架构与不可违反的边界
> - `.cursor/rules/axiom-quant.mdc` — 施工纪律（每个 PR 都受其约束）
>
> 阅读顺序：先读 `VISION.md`，再读本文第 0 章（审查结论）与第 1 章（P0 缺陷），然后按 `PHASE-1.5.md` 开工。

---

## 0. 审查结论

### 0.1 现状诚实评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构边界 | A− | `QuantEngine` ABC 干净，Controller 不碰 LEAN 内部，Strategy 不知道 broker。边界纪律优秀 |
| 结果真实性 | B | 真实 LEAN Docker 回测、真实 yfinance 数据、golden test 锁定。**没有假 alpha 曲线** |
| 前端质量 | B+ | 6 个页面真实可用，5 个诚实占位。设计系统落地度约 90% |
| 数据工程 | C− | 单标的硬编码、无 QA、无不可变快照、fallback 有静默错误路径 |
| 指标正确性 | C | 有 3 处会输出错误数字的缺陷（见 1.1） |
| 任务编排 | D | Celery 部署了但没用，线程跑回测，取消是假的，无超时 |
| 统计验证 | F | 完全不存在（这是"顶级"与"玩具"的分界线） |
| 工程基建 | D | 9 个测试、0 CI、0 认证、空 migration |

**总评：这是一个诚实、结构良好的 Phase 1 原型，地基比绝大多数同类项目扎实。但它距离"顶级量化研究产品"还差一个完整的量级，缺口不在功能数量，而在三件事：结果可信、统计可证、数据可复现。**

### 0.2 最重要的三个判断

这三条比后面所有功能清单都重要。

**判断一：一个量化研究产品的核心风险不是功能少，而是"输出可信但错误的数字"。**

用户做出的每一个投资决策都建立在你给的 Sharpe 上。目前有 3 条路径会静默输出错误数字（手续费被吞、alpha 是错的定义、Stooq fallback 产生未调整价格）。在补任何新功能之前，必须先消灭所有"静默错误路径"，并建立"宁可报错也不出错数"的原则。

**判断二：Validation（统计验证）必须先于 AI Strategy Lab 实现，原有 PRD 的阶段顺序需要调换。**

原 PRD 顺序是 Phase 2 = AI Strategy Lab，Phase 3 = Validation。这个顺序是危险的。AI 能以人类无法企及的速度批量生产策略——如果验证基建不存在，AI 的作用就是**过拟合放大器**：它会生产出几百个在样本内 Sharpe 2.0、样本外一文不值的策略，而系统无法分辨。

先建验证、再上 AI，AI 才是研究加速器；反之则是亏钱加速器。

**判断三：`试验次数（trial count）`必须现在就进数据模型，这是无法事后补算的架构决策。**

Deflated Sharpe Ratio 与 PBO 的计算都需要一个denominator：**"你在同一份数据上一共试了多少次？"** 如果不从现在开始记录每一次回测所针对的 `(数据快照, 标的池)` 组合，这个数字将永久丢失，DSR 永远算不出来。这件事必须在 Phase 1.5 完成，不能推迟。

---

## 1. P0：必须先修的正确性缺陷

**这一章的所有条目都是"输出错误结果"或"承诺了但没做到"级别的缺陷，优先级高于任何新功能。**

### 1.1 会输出错误数字的缺陷

#### P0-1 手续费被静默吞掉

`quant/metrics/performance.py` 的 `_parse_pct()` 无法解析带货币符号的字符串。已实测验证：

```python
_parse_pct("$43.00")   # -> None   ← LEAN 实际输出格式
_parse_pct("15%")      # -> 0.15   ← 正常
```

后果：`commission`、`total_transaction_costs` 永远是 `None`。用户看到的是"零成本回测"。golden run 的真实手续费 $43 从未出现在 UI 上。

**修复**：拆分为两个函数，`_parse_pct()` 只处理百分比，新增 `_parse_money()` 处理 `$`、`,`、负号、括号负数 `($43.00)`。为两者补齐单元测试矩阵。

#### P0-2 alpha 的定义是错的

`quant/metrics/performance.py:127-133`：

```python
benchmark_return = float(b.iloc[-1] / b.iloc[0] - 1.0)
alpha = total_return - benchmark_return
```

这是「超额收益（excess return）」，不是 alpha。真正的 alpha 需要对基准做回归：`r_p - r_f = α + β(r_m - r_f) + ε`。当策略 β ≠ 1 时（200DMA 策略经常空仓，β 显著小于 1），这个数字会严重误导——它把"因为仓位低而少跌"错记成"alpha"。

**修复**：
- 字段改名 `alpha` → `excess_return`，保留其现有语义（诚实）；
- 新增真正的 `alpha_capm`、`beta`，用 OLS 回归计算；
- 补 `information_ratio = mean(active_return) / tracking_error`。

#### P0-3 指标来源混用，tearsheet 内部自相矛盾

当前 `total_return`/`cagr`/`sharpe`/`max_drawdown` 优先取 LEAN 报告值，而 `sortino`/`calmar`/`volatility` 总是自算。最明显的矛盾：`calmar` 用自算 CAGR 除以 LEAN 的 max_drawdown，而同一份报告里 `cagr` 字段显示的是 LEAN 的 CAGR。两个数字对不上。

**修复方向（决策已定，不要再权衡）**：**所有指标一律自算**，LEAN 原始 statistics 全量存入 `extras` 仅作交叉校验。理由：
1. 内部一致性可保证；
2. 后续 rolling metrics / DSR / bootstrap 必须基于自算的日收益序列，无法从 LEAN 汇总值推导；
3. 换引擎时指标定义不变。

同时新增一个**对账测试**：自算值与 LEAN 值偏差超过阈值（Sharpe ±0.05、CAGR ±0.1%、MaxDD ±0.5%）时测试失败。这个测试是引擎正确性的哨兵。

#### P0-4 LEAN 输出 95% 被丢弃

`jobs/golden/.../Spy200DmaAlgorithm.json` 约 12,785 行，解析器只用了 `Charts`/`Statistics`/`Orders`。被丢弃的包括：

- `RollingWindow`：148 个滚动月度窗口，含 VaR95/99、Probabilistic Sharpe
- `TotalPerformance`：完整 TradeStatistics + ClosedTrades（含持仓周期、round-trip PnL）
- LEAN 已算好的 Beta、Information Ratio、Treynor、Tracking Error

**修复**：扩展 `quant/engine/result_parser.py`，把 `TotalPerformance.ClosedTrades` 解析为真正的 round-trip 交易（当前 `backtest_trades` 只有开仓记录，`exit_price`/`pnl`/`holding_period` 全空），并把 `RollingWindow` 落库供滚动指标图使用。

### 1.2 数据层静默错误路径（最危险）

#### P0-5 Stooq fallback 产生错误回测且无任何警告

`quant/data/providers.py:100-126` 的 fallback 链：yfinance 失败 → Stooq。但 Stooq 不提供股息/拆分数据，`_normalize()` 会填入 `dividends=0, stock_splits=0`。

后果链条：空的分红事件 → `build_factor_file()` 只生成终止行 `20501231,1,1,0` → 但策略仍用 `DataNormalizationMode.Adjusted` → **LEAN 拿到未调整价格却以为是已调整的**。SPY 年化分红约 1.5%，十年回测累计误差可达 15%+，而系统全程静默。

**修复**：
- `manifest.json` 增加 `corporate_actions_verified: bool` 与 `provider_capabilities` 字段；
- 若数据源不支持 corporate actions，**拒绝生成 factor file 并让回测直接失败**，错误信息明确指向数据源能力不足；
- 绝不允许"降级为静默近似"。

#### P0-6 无任何数据质量校验

从 vendor 到 LEAN 全链路零校验。缺失项：交易日缺口、OHLC 自洽性（`high >= max(open,close)`、`low <= min(open,close)`）、异常跳空（单日 >50% 且无对应拆分）、零成交量、重复时间戳、最后一根 bar 是否过期。

**修复**：新增 `quant/data/quality.py`，实现规则化校验器，返回结构化 `DataQualityReport`。**校验不通过则阻塞回测**（fail-closed），并在 Settings 页面展示报告。

#### P0-7 数据可覆盖，历史回测不可复现

`ingest_spy()` 每次全量重拉并覆盖 parquet，`manifest.json` 也被覆盖。旧回测记录的 `data_version` (sha256) 所指向的数据已经不存在。**这直接违反项目规则"Results must be reproducible for the same strategy + data + engine version"**。

**修复**：见 Phase 1.5 的不可变数据快照。

### 1.3 编排层 split-brain

#### P0-8 Celery 部署了但从未被使用

`services/api/services/backtests.py:129-136` 直接起 daemon 线程：

```python
import threading
from services.worker.tasks import execute_backtest
threading.Thread(target=execute_backtest, args=(bt_id,), daemon=True, ...).start()
```

全仓库没有任何 `.delay()` / `.apply_async()`。而 `docker-compose.yml` 里的 `worker` 服务在空转。连带后果：

- API 容器没有挂载 `docker.sock` → 用 `docker compose up` 起栈后，点"运行回测"必定失败
- `uvicorn --workers N` 会产生 N 份互不协调的容器启动
- API 重启 → 线程消失 → 回测永久卡在 `RUNNING`，无任何清理任务
- `AXIOM_DOCKER_HOST`（compose 中定义）和 `AXIOM_SYNC_BACKTESTS`（.env.example 中定义）都是死配置，代码从不读取

#### P0-9 取消功能是假的

`cancel_backtest()`（`services/api/services/backtests.py:140-164`）只把 DB 状态改成 `CANCELLED`，**从不调用 `engine.cancel_backtest()`**。LEAN 容器继续跑完。而 `quant/engine/lean.py:161` 的 `subprocess.run()` 是阻塞调用且**没有 timeout 参数**——一个卡死的 LEAN 会永久占用 2 CPU / 2GB。

**修复**：Celery 任务化 + Redis 撤销信号 + `subprocess.run(timeout=...)` + 容器 `docker kill` + 启动时的孤儿任务回收（reconciliation job）。

#### P0-10 Alembic migration 是空的

`services/api/alembic/versions/0001_initial.py` 的 `upgrade()` 是 `pass`，运行时靠 `Base.metadata.create_all()`。这意味着**schema 无法演进**——后续所有阶段都要加表，没有 migration 就只能删库重建。

**修复**：立即用 `alembic revision --autogenerate` 生成真实的 baseline，并在容器 entrypoint 加 `alembic upgrade head`。

---

## 2. 路线图重排

### 2.1 与原 PRD 的映射

| 新顺序 | 阶段 | 对应原 PRD | 变更理由 |
|--------|------|-----------|---------|
| 1 | **Phase 1.5 可信性加固** | 新增 | 修 P0，建立不可变数据与试验台账 |
| 2 | **Phase 2 数据平台化** | 原 Phase 6 部分 | 多资产是后续一切的前提 |
| 3 | **Phase 3 统计验证引擎** | 原 Phase 3 ✅ 提前 | **护城河。必须先于 AI** |
| 4 | **Phase 4 研究工作台** | 原 Phase 6 部分 | 研究速度 |
| 5 | **Phase 5 AI Copilot** | 原 Phase 2 ⚠️ 推后 | 在验证保护下才安全 |
| 6 | **Phase 6 Paper Trading** | 原 Phase 4 | 不变 |
| 7 | **Phase 7 Live Trading** | 原 Phase 5 | 不变 |
| 8 | **Phase 8 组合与归因** | 原 Phase 6 | 单策略 → 多策略组合 |

### 2.2 前端导航的处置

`apps/web/src/components/layout/nav.ts` 当前把 5 个未来页面放在"稍后"分组，`experiments` 标为"第三阶段及以后"。按新顺序，`/experiments` 与 `/validation`（新增）会先于 AI 上线，需同步更新占位文案中的阶段号，避免前后端对阶段的表述不一致。

---

## 3. Phase 1.5 — 可信性加固

**目标：让系统输出的每一个数字都可信、可复现，且永不静默出错。**
**预估：3–4 周 / 9 个工作包。这是所有后续工作的地基，不允许跳过或部分完成。**

> **可执行任务清单见 `docs/PHASE-1.5.md`** —— WP-0 到 WP-8，每个工作包对应一个 PR，含逐条验收标准与阶段 DoD。
> 本章只保留两个架构级 schema 定义，因为任务清单会引用它们。

### 3.2 不可变数据快照（架构级）

引入内容寻址的数据快照，替代"覆盖式" ingest。

新增 `data_snapshots` 表：

| 字段 | 说明 |
|------|------|
| `id` | UUID |
| `snapshot_key` | 内容哈希，形如 `spy-daily-2026-08-31-a1b2c3` |
| `symbols` | JSON，快照包含的标的 |
| `resolution` | `daily` / `minute` |
| `provider` | `yfinance` / `stooq` / `polygon` |
| `date_range_start` / `date_range_end` | 数据覆盖区间 |
| `row_count` | 行数 |
| `content_sha256` | 全量内容哈希 |
| `corporate_actions_verified` | 布尔，见 P0-5 |
| `quality_report` | JSON，见 P0-6 |
| `created_at` | 摄取时间（≠ 数据 as_of） |
| `superseded_by` | 指向新快照，形成血缘链 |

磁盘布局改为不可变：`data/snapshots/{snapshot_key}/...`，`data/market/` 保留为指向 latest 的符号链接以兼容现有代码。

`backtests` 表新增 `data_snapshot_id` 外键（替代当前的裸字符串 `data_version`）。

**验收标准**：
- 重跑一个三个月前的回测，得到逐点相同的 equity 曲线；
- golden test 断言 `data_snapshot_id` 与 `engine_version` 均匹配预期值（当前 golden test 完全没检查这两项）；
- 新 ingest 不删除旧快照，只写 `superseded_by`。

### 3.3 试验台账（Trial Ledger）— 不可推迟

这是判断三的落地。新增 `experiment_trials` 表，**每一次回测都必须写入一行**：

| 字段 | 说明 |
|------|------|
| `id` | UUID |
| `backtest_id` | 外键 |
| `data_snapshot_id` | 外键 —— 多重检验的分组键 |
| `universe_key` | 标的池标识 |
| `strategy_family` | 策略族标识（同一 idea 的不同参数视为同族） |
| `parameters` | JSON，本次试验的参数 |
| `parameter_hash` | 去重用 |
| `observed_sharpe` | 本次结果 |
| `is_oos` | 是否样本外 |
| `created_at` | |

有了它，`SELECT count(*) ... GROUP BY (data_snapshot_id, strategy_family)` 就是 DSR 需要的 N。

**验收标准**：任意策略族可查询"至今在此数据快照上试过 N 次，Sharpe 分布如何"。

### 3.4 本阶段其余内容

编排层收敛到 Celery、超时与真实取消、孤儿回收、Alembic 真实 baseline、CI、结构化日志、`/health` 真实探活、列表分页、策略状态机守卫、测试从 9 个补到 ~80 个——全部展开在 `docs/PHASE-1.5.md` 的 WP-0 / WP-6 / WP-7 / WP-8。

---

## 4. Phase 2 — 数据平台化与多资产

**目标：从"只能跑 SPY"到"能跑任意标的池"，并具备机构级数据血缘。**
**预估：4–5 周。**

### 4.1 解除 SPY 硬编码

当前 SPY 硬编码遍布各层，需逐一参数化：

| 文件 | 当前 | 改为 |
|------|------|------|
| `quant/data/providers.py` | `fetch_spy_daily()` | `fetch_daily(symbol, ...)` |
| `quant/data/ingest_spy.py` | 路径/文件名硬编码 | `ingest(symbols: list[str], ...)` |
| `quant/data/lean_converter.py` | `convert_spy_to_lean()`、`spy.zip` | `convert_to_lean(symbol)`、`{symbol}.zip` |
| `quant/data/duckdb_query.py` | 单一 `spy_daily` view | 按快照注册多标的 view |
| `quant/engine/lean.py` | 无条件 `ensure_lean_spy_data()` | 按 request 的 universe 准备数据 |
| `quant/engine/base.py` | `BacktestRequest` 无 symbol 字段 | 新增 `universe: list[str]` |

好消息：provider 层的 `fetch_yfinance(symbol=...)` 已经是参数化的，约 60% 管线本身与标的无关。

### 4.2 标的池（Universe）作为一等实体

新增 `universes` 表 + `universe_members` 表，支持：静态列表、规则筛选（市值/流动性/行业）、**时点正确的成分变动**（`effective_from` / `effective_to`）。

时点正确的成分历史是消除**生存者偏差**的唯一手段。当前的静态 map file `20000101,spy` 无法支持退市股票轮转。若做多股票策略而不解决这一点，所有回测结果都会系统性偏高。

### 4.3 数据源升级与交叉对账

- 接入 Polygon（`.env.example` 已预留 key，adapter 未实现）作为主源，yfinance 降级为对账源；
- **双源对账**：同一标的同一日的 close 偏差超过阈值（如 10 bps）则标记该 bar 为 suspect 并进入 quality report；
- 分红/拆分事件必须双源一致才写入 factor file。

### 4.4 增量摄取

当前每次全量重拉。改为按日期增量 append + 定期全量校验（检测 vendor restatement）。restatement 必须产生新快照，不得原地修改。

**验收标准**：
- 能一条命令摄取 500 支股票日线并生成对应 LEAN 数据；
- 能跑一个 10 标的的横截面策略回测；
- 对账报告能指出至少一个 yfinance 与 Polygon 不一致的历史 bar；
- 摄取一支已退市股票，其在 universe 中的 `effective_to` 被正确记录。

---

## 5. Phase 3 — 统计验证引擎（护城河）

**目标：让系统能主动告诉用户"你这个策略大概率是过拟合的"。**
**预估：5–6 周。这是本路线图中技术含量最高、最难被复制的部分，也是"顶级"二字的真正来源。**

### 5.1 为什么这是护城河

任何人都能做出"跑回测 + 画曲线"的产品。真正稀缺的能力是**告诉用户他的策略是假的**。这需要：正确实现一批统计检验、把它们做成阻塞式流程（而不是可选报告）、并用产品设计让用户无法绕过。

### 5.2 检验清单（按实现优先级）

#### 5.2.1 Walk-Forward 与样本外纪律

- 滚动窗口：train N 年 → test M 年 → 前滑，覆盖全历史；
- Anchored（扩张窗口）与 Rolling（固定窗口）两种模式；
- **产品级约束**：策略状态机中，未通过 walk-forward 的策略不允许进入 `VALIDATED` 状态（`StrategyStatus` 枚举已定义 `VALIDATED`，但目前没有任何逻辑守卫它——`PATCH /strategies/{id}` 可以随意改状态）；
- 前端呈现：每个 fold 的 IS/OOS Sharpe 对比条形图 + OOS 拼接后的净值曲线。

#### 5.2.2 Deflated Sharpe Ratio（DSR）

参考 Bailey & López de Prado (2014), *The Deflated Sharpe Ratio*。

输入：观测 Sharpe、试验次数 N（来自 3.3 试验台账）、试验间 Sharpe 方差、收益序列的偏度与峰度、样本长度 T。
输出：经过多重检验与非正态修正后的 Sharpe，以及"该 Sharpe 为真"的概率。

**这个数字应该显示在 tearsheet 最顶部，比原始 Sharpe 更醒目。**

#### 5.2.3 PBO（过拟合概率）via CSCV

参考 Bailey et al. (2015), *The Probability of Backtest Overfitting*。

实现 Combinatorially Symmetric Cross-Validation：收益序列切成 S 份（如 S=16），枚举 C(S, S/2) 种训练/测试划分，每次取样本内最优配置，观察其样本外排名；PBO = 样本内最优配置在样本外落入中位数以下的比例。

PBO > 0.5 意味着"你的最优参数在样本外表现低于中位数的概率超过一半"——应触发红色警示。

#### 5.2.4 参数敏感性与稳健性平台

对参数做网格扰动，绘制 Sharpe 响应曲面。核心判断：最优点是**孤峰**（knife-edge，过拟合特征）还是**高原**（plateau，稳健特征）。这是从业者最直观有效的过拟合识别手段之一，实现成本也低。

#### 5.2.5 成本敏感性与盈亏平衡成本

逐步提高手续费与滑点，求出 alpha 归零的临界成本。输出一句话结论："该策略在单边成本超过 X bps 时失效"。若 X 低于该标的的真实成本量级，策略即刻判死。

（注意：这依赖 P0-1 的手续费修复，否则成本基线本身是错的。）

#### 5.2.6 Bootstrap 置信区间

用 stationary bootstrap / block bootstrap（保留收益自相关结构，不能用简单 iid 重抽样）给出 Sharpe、CAGR、MaxDD 的置信区间。让用户看到"Sharpe = 1.2 [95% CI: 0.3, 2.1]"——区间跨零则无统计显著性。

#### 5.2.7 制度（Regime）稳定性

按市场状态分段检验：牛/熊、高波动/低波动、加息/降息周期，以及若干指定压力窗口（2008、2020-03、2022）。输出各制度下的 Sharpe 与胜率。一个只在单一制度有效的策略必须被明确标注。

#### 5.2.8 多重检验校正（跨策略）

White's Reality Check 与 Hansen's SPA test，用于回答"在我筛过的这一批策略里，最好的那个是否真的有 edge"。这是 Phase 5 AI 大批量生成策略后的必备闸门。

### 5.3 验证作为一等实体

新增 `validation_runs` 表：关联 `strategy_version_id`、检验类型、参数、结果 JSON、通过/失败、执行时间。
新增前端页面 `/validation`：验证流水线的进度与报告；`/experiments` 页面从占位升级为参数扫描的真实实现。

### 5.4 验收标准

- 用一个**故意过拟合**的策略（在 SPY 上暴力搜索出的最优双均线参数）跑完整验证流水线，系统必须给出 PBO > 0.5 且 DSR 显著低于原始 Sharpe 的结论；
- 用 SPY 200DMA 跑，结论应为"edge 微弱但非过拟合产物"（其真实 CAGR 仅 1.3%，golden test 已证实——这是很好的诚实基线）；
- 未通过验证的策略在 UI 上无法被标记为 `VALIDATED`；
- 所有统计量都有单元测试，且用文献中的已知数值案例做校验。

---

## 6. Phase 4 — 研究工作台

**目标：把"改代码 → 等回测 → 看图"的循环从分钟级压到秒级，并让分析深度达到专业 tearsheet 水平。**
**预估：4–5 周。**

### 6.1 回测速度

当前每次回测都是完整 Docker 冷启动。改进：
- 常驻 worker 容器池，避免重复冷启；
- 结果缓存：`(strategy_code_hash, data_snapshot_id, date_range, params)` 命中则直接返回历史结果（这也顺便防止重复试验污染试验台账）；
- 参数扫描并行化（Celery group / chord）。

### 6.2 完整 Tearsheet

现有 12 个指标 tile + 3 张图（净值、回撤、月度表格）。补齐专业分析需要的：

- **滚动指标**：滚动 Sharpe / β / 波动率 / 相关性（数据源已在 LEAN 的 `RollingWindow` 里，见 P0-4）
- **收益分布**：直方图 + QQ 图 + 偏度/峰度 + 尾部比（tail ratio）
- **风险**：VaR / CVaR（LEAN 已算，被丢弃）
- **持仓与暴露时间序列**：LEAN 的 Exposure / Turnover chart 目前未解析
- **交易分析**：真正的 round-trip 交易表（当前 `backtest_trades` 的 `exit_price`/`pnl`/`holding_period` 全为空）、持仓周期分布、MAE/MFE
- **净值图增强**：对数坐标、基准归一化、回撤阴影叠加、交易标记
- **多回测对比**：叠加两条以上净值曲线（当前完全无法对比）
- **导出**：PDF / HTML tearsheet（`/reports` 页面从占位升级）

### 6.3 研究笔记

`/reports` 页面实现可版本化的研究文档：假设 → 检验 → 结论 → 失效模式记录。这是 `builder-panel.tsx` 里"假设"字段应有的归宿（当前它只是个不影响任何逻辑的元数据框）。

### 6.4 策略编辑器升级

Monaco 已接入但功能最小。补：Python LSP（补全/悬停/诊断）、提交前语法校验、回测失败的错误行内定位、**版本 diff 视图**（`version-history.tsx` 目前只能点击加载，无法对比）。

### 6.5 前端工程债

- `packages/shared-types` 未被使用，前端在 `lib/api.ts` 里手工维护重复类型 → 改为从 FastAPI OpenAPI 自动生成；
- 前端测试当前为 **0** → 补 Vitest 单测 + Playwright 关键路径 E2E；
- 已安装未使用的依赖（`@tanstack/react-table`、`date-fns`）→ 用于新交易表或移除；
- 中文文案硬编码 → 若有国际化打算，此时抽 i18n 成本最低。

---

## 7. Phase 5 — AI Copilot（在验证保护之下）

**目标：AI 加速研究，而不是加速过拟合。**
**预估：4–5 周。**

### 7.1 不可逾越的约束

这几条是产品的伦理底线，实现时不得妥协（项目规则已明确"AI must not modify system risk limits"）：

1. **AI 不能修改风控限额** —— 风控配置的写入路径必须完全绕开 AI，代码层面隔离；
2. **AI 不能标记策略为已验证** —— 只有验证流水线的实际结果能改变策略状态；
3. **AI 生成的每个策略都必须走完整验证** —— 没有"快速通道"；
4. **AI 的每次试验都写入试验台账** —— 这是 DSR 的 N，AI 高频试错必须计入多重检验惩罚，否则 DSR 会被系统性高估；
5. **不做假聊天** —— 没有真实能力支撑的对话界面不上线。

### 7.2 功能

- 自然语言 → LEAN 策略代码骨架（用户必须审阅后才能运行）；
- 回测结果解读：自动指出"这个 Sharpe 主要来自 2020 年 3 月的单次反弹"这类洞察；
- 失效模式诊断：结合 regime 分析解释策略何时失效；
- 研究建议：基于试验台账提示"你已在此数据上试了 47 次，继续搜索的多重检验惩罚已很重"。

**最后这一条是 AI 在量化产品中最有价值也最诚实的用法：劝用户停下来。**

---

## 8. Phase 6 / 7 — Paper 与 Live Trading

**目标：从研究走到执行，且执行结果可与回测对账。**
**预估：Paper 4 周，Live 5 周。**

### 8.1 风控引擎实体化

`quant/risk/base.py` 目前是装饰性的：定义了 `RiskEngine` ABC 和 `PassThroughRiskEngine`，**全仓库无任何地方 import 它**。

Live 之前必须实现真实风控：单标的仓位上限、组合杠杆上限、日内亏损熔断、回撤熔断、集中度限制、订单速率限制。链路必须是 `Strategy → Risk → Execution → Broker`，风控独立于策略代码且不可被策略绕过。

### 8.2 回测–实盘对账（最容易被忽略但最重要）

同一策略同一天，回测应产生什么信号、实盘实际发了什么单、成交价与回测假设价差多少。**持续的对账偏差是回测失真的唯一客观证据**。这个功能决定了整个研究体系是否值得信任。

### 8.3 其他

- Alpaca paper 接入（key 已在 `.env.example` 预留）；
- 订单/持仓/成交数据模型（当前完全没有这些表）；
- 一键停机（kill switch）与停机审计；
- 实时监控与告警。

---

## 9. Phase 8 — 组合与归因

**目标：从"单策略"到"策略组合"。**
**预估：4 周。**

- 多策略相关性矩阵与组合构建（等权、风险平价、均值方差、层次风险平价 HRP）；
- 组合层面的风险预算与回撤归因；
- 因子暴露分析：对 Fama-French 三/五因子 + 动量做回归，回答"这是真 alpha 还是 beta 伪装"——**这是判断策略是否值得投入真金白银的终极检验**；
- Brinson 归因（若做多资产/行业配置）。

---

## 10. 贯穿性工程基建

这些不属于单一阶段，但决定产品能否成为"产品"而非"脚本集"。

### 10.1 认证与多用户（Phase 2 前必须完成，若有他人使用）

当前**零认证**，所有接口公开。`users` 表存在但完全孤立：没有任何表有 `user_id` 外键，`StrategyVersion.created_by` 是硬编码字符串 `"local"`，审计日志的 actor 永远是 `"local"`。

未认证的 `POST /data/ingest/spy` 是一个任何人都能触发的网络+磁盘 DoS 入口。

需要：认证（OAuth / JWT）、`user_id` 外键贯穿业务表、行级隔离、审计日志记录真实 actor、审计日志的读取 API（当前只写不读）。

### 10.2 可观测性

结构化日志 + Prometheus 指标（回测时长、失败率、队列深度）+ Sentry + OpenTelemetry 链路追踪。回测的 Docker stdout/stderr 目前只落磁盘（`jobs/{id}/docker_*.log`），应可通过 API 查看。

### 10.3 安全

- 用户提交的任意 Python 在 LEAN 容器内执行。当前隔离仅靠 `--network none` + 资源限制，尚可，但需补：seccomp profile、只读根文件系统、非 root 用户、禁用危险 import 的静态检查；
- `docker-compose.yml` 与 `alembic.ini` 里的默认口令 `axiom:axiom` 已提交进仓库，需改为环境变量注入；
- CORS 当前是 `allow_credentials` 的宽松配置。

### 10.4 版本控制

**项目当前不是 git 仓库**（`git log` 报错）。一个金融研究产品必须有完整的代码史与可审计的变更记录。这应该是**第一件事**——在动任何代码之前 `git init` 并提交当前状态作为基线。

---

## 11. 建议执行顺序与里程碑

| 里程碑 | 内容 | 累计周期 | 完成后的能力 |
|--------|------|---------|-------------|
| **M0** | `git init` + 基线提交 | 0.5 天 | 变更可追溯 |
| **M1** | Phase 1.5 全部 | ~4 周 | 数字可信、结果可复现、编排可靠 |
| **M2** | Phase 2 数据平台 | ~9 周 | 多资产、无生存者偏差、数据可对账 |
| **M3** | Phase 3 验证引擎 | ~15 周 | **能主动识别过拟合 —— 达到"顶级"的门槛** |
| **M4** | Phase 4 研究工作台 | ~20 周 | 专业级分析深度与研究速度 |
| **M5** | Phase 5 AI Copilot | ~25 周 | AI 加速研究（受验证约束） |
| **M6** | Phase 6/7 Paper + Live | ~34 周 | 研究到执行闭环、回测实盘对账 |
| **M7** | Phase 8 组合归因 | ~38 周 | 多策略组合与真 alpha 判定 |

**如果只能做三件事**：M1（可信）、M3（可证）、以及 Phase 4 里的完整 tearsheet。这三件事完成后，产品已经强于市面上绝大多数零售量化平台。

---

## 12. 施工纪律

完整纪律见 `.cursor/rules/axiom-quant.mdc`（该文件 `alwaysApply: true`，会自动注入每次会话）。三条最容易被违反的：

1. **不要在验证引擎（Phase 3）之前实现 AI 策略生成。** 顺序颠倒会让 AI 变成过拟合放大器。
2. **不要在数据快照（Phase 1.5）之前扩展多资产。** 不可复现的问题会被放大 N 倍。
3. **不要为了让 golden test 通过而放宽容差。** 数字变了就去查为什么。

以及一条隐性纪律：**遇到"这里近似一下应该没关系"的念头时，停下来重读 `docs/VISION.md` 信念一。** 代码库里最危险的缺陷（P0-5）正是这个念头的产物。

---

## 附录 A：P0 缺陷速查表

| ID | 缺陷 | 位置 | 影响 |
|----|------|------|------|
| P0-1 | 手续费解析失败，永远为 None | `quant/metrics/performance.py` `_parse_pct` | 报告零成本 |
| P0-2 | alpha 定义错误（超额收益冒充 alpha） | `quant/metrics/performance.py:127-133` | 误导性风险调整收益 |
| P0-3 | LEAN 值与自算值混用，tearsheet 自相矛盾 | `quant/metrics/performance.py:150-180` | 内部不一致 |
| P0-4 | LEAN 输出 95% 被丢弃（含 Beta/IR/VaR/滚动窗口） | `quant/engine/result_parser.py` | 分析深度缺失 |
| P0-5 | Stooq fallback 静默产生未调整价格 | `quant/data/providers.py:100-126` | **回测结果错误且无警告** |
| P0-6 | 全链路无数据质量校验 | `quant/data/*` | 脏数据静默进入回测 |
| P0-7 | ingest 覆盖式写入，历史回测不可复现 | `quant/data/ingest_spy.py` | 违反可复现原则 |
| P0-8 | Celery 部署未用，线程跑回测，重启产生孤儿 | `services/api/services/backtests.py:129-136` | compose 下回测直接失败 |
| P0-9 | 取消是假的，且 LEAN 调用无超时 | `services/api/services/backtests.py:140-164`、`quant/engine/lean.py:161` | 资源泄漏 |
| P0-10 | Alembic migration 为空 | `services/api/alembic/versions/0001_initial.py:19-22` | schema 无法演进 |

## 附录 B：关键文献

统计验证部分的实现请以原始文献为准，不要凭记忆推导公式。

- Bailey, D. & López de Prado, M. (2014). *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality.*
- Bailey, D., Borwein, J., López de Prado, M. & Zhu, Q. (2015). *The Probability of Backtest Overfitting.*
- Bailey, D. et al. (2014). *Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance.*（含 Minimum Backtest Length）
- White, H. (2000). *A Reality Check for Data Snooping.*
- Hansen, P. R. (2005). *A Test for Superior Predictive Ability.*
- Politis, D. & Romano, J. (1994). *The Stationary Bootstrap.*
- López de Prado, M. (2018). *Advances in Financial Machine Learning.*（CSCV、组合构建、HRP）
