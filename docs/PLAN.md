# Axiom Street — 最终执行计划

> **本文取代 `docs/ROADMAP.md`。** 审计与复核基准：2026-09-04（19 个 commit，304 个受版本控制文件）。
>
> **文档体系（收敛后共 5 份）**
>
> | 文档 | 职责 | 变更频率 |
> |------|------|---------|
> | `docs/VISION.md` | 产品宪法：是什么、为谁、**明确不做什么**。冲突时以它为准 | 几乎不变 |
> | `docs/PLAN.md` | **本文**：定位结论 + 现状 + 全部待办与顺序。唯一的计划来源 | 每完成一个工作包更新 |
> | `docs/architecture.md` | 目标架构、不可违反边界、**已实现行为的规格** | 随实现变更 |
> | `docs/data-sources.md` | 数据源能力与摄取契约 | 随数据层变更 |
> | `design-system/axiom-street/MASTER.md` | 设计令牌与反模式 | 随 UI v2 重写 |
>
> `.cursor/rules/axiom-street.mdc` 是施工纪律（`alwaysApply: true`），不是文档，单独维护。
>
> 阅读顺序：`VISION.md` → 本文第 1、2 章 → 当前工作包章节。

---

## 1. 定位结论（本次审计已锁定）

### 1.1 一句话

**Axiom Street 是一个让你难以自欺的量化研究环境。** 不追求最快的回测器，而是最诚实的那个。

完整信念体系见 `docs/VISION.md`，六条信念仍然全部成立，不修改。

### 1.2 三个此前悬空、现已定性的定位问题

这三条是本次审计的核心产出。它们此前从未被明确写下，导致仓库里出现了互相矛盾的实现。

| # | 问题 | 结论 | 直接后果 |
|---|------|------|---------|
| **D1** | 两个前端谁是产品？ | **`apps/web` 是唯一产品。** `apps/terminal` 的**视觉语言**升级进 `apps/web`，其代码整体删除 | 删 4,403 行；design system 升级为 v2 双主题 |
| **D2** | 单人自用还是对外产品？ | **单人自用，短期不开放。** 认证不做，改为部署约束 | 认证/多用户从"P0 技术债"降级为 Phase 6 前置项，省 2–3 周 |
| **D3** | 语言收口 | **中文界面 + 英文对外文档。** UI 文案抽成 i18n 字典，`README`/`NOTICE` 英文，`docs/` 中文 | 新增 `locales/zh-CN.ts`，预留 `en.ts` 空壳 |

### 1.3 D1 的判定依据（为什么删掉最新的工作）

`apps/terminal` 是最近两个 commit 的产物，但它同时违反三条**项目自己写的铁律**：

| 铁律来源 | 条文 | `apps/terminal` 的实际状态 |
|---------|------|--------------------------|
| `.cursor/rules` L18 | Mock data 只许用于空态 / Storybook，**永不冒充回测结果** | `mocks/engine.ts` + `lib/prng.ts` 共 959 行，用 mulberry32 + Box–Muller 合成净值、指标、成交、月度热力图，直接渲染成 tearsheet |
| `.cursor/rules` L14–15、L17 | **Phase 5 (AI Copilot) 不得在 Phase 4 质量到位前启动** | `components/shell/copilot.tsx` 266 行 + `mocks/copilot.ts` 113 行，是一个照本宣科的假对话框 |
| `MASTER.md` 反模式 | 禁 cyberpunk black；`VISION` 信念六指定白底 + 单一主色 `#1677FF` | `#0a0a0b` 近黑底 + `#e3b341` 琥珀强调 |

此外它不在 `docker-compose.yml`、不在 CI、不在 `architecture.md` 的仓库布局表里——**它是一个没有被任何契约承认的第二前端**。

**但它的视觉工程本身是这个仓库里最好的**（见 6.1 的令牌收割清单）。所以结论不是"否定它"，而是"把它值钱的部分搬走，把违规的部分删掉"。

### 1.4 D2 的部署约束（替代认证）

不做认证的前提是**永不暴露**。以下三条写进 `README` 与 `docker-compose.yml`：

- API 与 Web 只绑 `127.0.0.1`，不绑 `0.0.0.0`；
- `POST /api/v1/data/ingest` 是一个任何人都能触发的网络+磁盘 DoS 入口，这是**已知且被接受的风险**，前提是它不可从外部到达；
- `users` 表、`created_by="local"`、`audit_logs.actor="local"` 保持现状，标注为**已知空壳**，不假装它们有意义。

一旦有第二个人使用，认证与 `user_id` 贯穿立刻升级为 P0，插在当期工作包之后。

---

## 2. 现状诚实评估（2026-09-04 复核）

`ROADMAP.md` §0.1 的评分表基准是 2026-08-31，**8 项里有 5 项已经过时**。下表是复核后的真实状态，并给出证据。

| 维度 | 旧评分 | 复核 | 证据 |
|------|-------|------|------|
| 架构边界 | A− | **A−** | `grep` 确认 `quant/` 零 import FastAPI / Celery / SQLAlchemy / services；Controller 不碰 LEAN 内部 |
| 结果真实性 | B | **A−** | 真实 LEAN Docker、golden test 锁定 CAGR 1.308% / Sharpe 0.136 |
| 统计验证 | **F** | **A−** | 7 类检验全部落地（WF / DSR / PBO / 敏感性 / 成本 / bootstrap / regime / SPA_c），且是阻塞式闸门 |
| 任务编排 | **D** | **B+** | Celery + 真取消 + 超时 + 孤儿回收 + Beat；`threading.Thread` 路径已消除 |
| 工程基建 | **D** | **B** | 349 个 Python 测试 / 51 文件（旧记录 9 个）；CI + nightly golden；9 个真实 Alembic migration |
| 指标正确性 | C | **A−** | P0-1/2/3 已修：`_parse_money`、`excess_return` 改名 + `alpha_capm`/`beta`、全部自算 + 对账测试 |
| 数据工程 | C− | **B+** | 不可变内容寻址快照、`quality.py` fail-closed、双源对账、PIT universe、增量摄取、token bucket 限速 |
| **前端质量** | B+ | **C+** ↓ | 见下方三条，这是**当前唯一明显落后于后端的维度** |

### 2.1 唯一的短板：前端

| 问题 | 量化 |
|------|------|
| 测试覆盖 | 后端 349 个测试 / 前端 **18 个**，且全在 4 个纯函数文件（`api-list` / `diff` / `labels` / `tearsheet`）。**9,133 行 UI 零组件测试、零 E2E** |
| 令牌纪律 | 存在 `--as-*` 令牌 + tailwind `as.*` 色阶，但仍有 **34 处硬编码 hex 散在 12 个文件**，图表层最严重（7 个图表文件里 5 个） |
| 结构失衡 | `validation-desk.tsx` 668 行、`backtest-studio.tsx` 653 行、`settings/page.tsx` 411 行（逻辑直接写在路由文件，与其余全部走 `features/` 的约定不符） |

### 2.2 计划文档自身的三处失真

这是"历史计划必须删除"的直接证据——**过时的计划正在提供错误信息**：

| 位置 | 文档声称 | 实际 |
|------|---------|------|
| `ROADMAP.md` §10.4 | 「项目当前不是 git 仓库」，并把 `git init` 列为 M0 里程碑 | 19 个 commit，M0 早已完成 |
| `ROADMAP.md` §6.2 结尾 | 「未做：round-trip 配对」 | **已做**：`result_parser.py:96 _closed_trades()` 解析 `TotalPerformance.ClosedTrades`，产出 `exit_price`/`pnl`/`holding_period`，`_orders_as_trades` 仅作降级；`tests/unit/test_parser_closed_trades.py` 已覆盖 |
| `README.md` 状态表 vs `data-sources.md` vs `.cursor/rules` | 三处对当前阶段的说法互相矛盾：`Phase 2 In progress` / `Phase 2 已关闭` / `Active phase: Phase 4` | 真实状态：Phase 1.5 / 2 / 3 已关闭，Phase 4 约 90% |

**结论：真实阶段 = Phase 4 研究工作台收尾。** 这个数字必须只在一处声明（本文第 7 章），其余文档一律指向本文。

---

## 3. 执行总览

五个工作包，严格顺序。顺序不是偏好，是依赖：**先消除矛盾 → 再删除 → 再重构 → 再重做 UI → 再加功能**。

| 包 | 内容 | 工期 | 为什么在这个位置 |
|----|------|------|----------------|
| **W0** | 文档融合与删除 | 1 天 | 最便宜且解除所有下游歧义。带着三处互相矛盾的阶段声明干活，每个决策都要先考古 |
| **W1** | 垃圾代码清除 | 2–3 天 | **删除必须先于重构**——不要重构即将删掉的代码 |
| **W2** | 架构整理（验证注册表） | 1.5–2 周 | 定义 `ValidationSpec`，W3b 的单一表单要靠它驱动 |
| **W3** | 前端 UI v2 | 2–3 周 | W3a（令牌/主题）可与 W2 并行；W3b（表单收敛）依赖 W2 |
| **W4** | Phase 4 收尾 + 后续路线 | 1 周 + 见第 7 章 | 收尾项少，但必须在 Phase 5 之前关闭 |

累计到"可以开 Phase 5"约 **6–8 周**（单人）。

---

## 4. W0 — 文档融合与删除（1 天）

当前 7 份文档共 ~1,390 行，收敛为 5 份。

### 4.1 删除

| 文件 | 处置 | 理由 |
|------|------|------|
| `docs/ROADMAP.md`（593 行） | **删除**，内容按 4.2 分流 | 它是一份施工计划，但其中 §1（P0-1…P0-10，~90 行）全部已修、§3 Phase 1.5 已关闭、§4 Phase 2 已关闭、§5 Phase 3 已关闭、§0.1 评分表 8 项错 5 项、§10.4 事实性错误、§11 里程碑 M0–M3 已完成。**剩下的有效信息不足 30%，且与其余文档冲突** |

不做 `docs/archive/`。git 历史就是归档——`git show 3bf97fc:docs/ROADMAP.md` 永远可取回。再留一份"历史计划"文件，本次整理就白做了。

### 4.2 抢救：把"已交付"规格搬走（这是删除前的必做步骤）

`ROADMAP.md` 里的 `> 已交付：…` 注记**不是计划，是规格**。它们记录了 7 类验证检验的判定口径，是仓库里唯一写下这些口径的地方，删掉就永久丢失。搬迁目标：

**新建 `docs/validation-gates.md`** — 收录 8 个闸门的完整判定规则，从 ROADMAP §5.2.1–5.2.8 抢救，包括：

- Walk-forward：拼接 OOS Sharpe（非折均值）；IS 均值 > 0.5 且拼接 OOS < 0 判定塌缩
- DSR：≥ 95%，N 取自 `experiment_trials`
- PBO / CSCV：≤ 0.5；S 取能整除 T 的最大偶数 ∈{16…4} 且每份 ≥ 10 根，否则失败而非丢交易日
- 敏感性：峰值周围连续 ≥3 点落在 0.5 Sharpe 带宽内 = 高原
- 成本：单边成本全计入 `slippage_bps`，对 `alpha_capm` 线性插值求临界；网格必须含 0 bps；临界 ≤ 真实成本（默认 5 bps）判死
- Bootstrap：Politis–Romano geometric blocks，块长用 Politis–White AR(1) plug-in，**禁 iid**；Sharpe 95% 区间下界 ≤ 0 不通过；< 252 交易日失败而非报窄区间
- Regime：牛熊按**基准** 20% 峰谷（非策略曲线）；高低波动按 21 日实现波动 vs 样本中位数；利率按 FOMC 生效日；各轴 ≥ 60 交易日；压力窗口只报告不闸门
- SPA：Hansen SPA_c 为闸门（p < 0.05 且 T > 0），同时报 White RC 与 SPA_l/SPA_u；≥ 2 条可区分试验 + 252 共同交易日；> 64 条拒绝截断

**并入 `docs/architecture.md`** — ROADMAP §6.1 的缓存键定义（`(strategy_code_hash, data_snapshot_id, engine_version, date_range, params)` 命中不写第二行试验台账）、LEAN slot 池语义、`STREET_SCAN_PARALLELISM`「不用 chord，父等子会在 concurrency=2 死锁」这条踩坑记录。

### 4.3 重写

| 文件 | 动作 |
|------|------|
| `README.md` | 状态表改为**只有一行**：`当前阶段：Phase 4 研究工作台收尾 → 见 docs/PLAN.md`。删掉逐 Phase 的 ✓ 清单（它是 `data-sources.md` 与本文的第三份不一致来源）。加 1.4 的部署约束警告。文档表里 `ROADMAP.md` → `PLAN.md`，新增 `validation-gates.md` |
| `docs/architecture.md` | 仓库布局表删 `apps/terminal`、`packages/`、`quant/risk`（按 W1 结果）；§5 技术选型表删 DuckDB 行（见 5.4）；§7 安全模型改写为 D2 的"不暴露"模型而非"待补认证" |
| `design-system/axiom-street/MASTER.md` | 全文重写为 v2 双主题，见 6.1。现版本仅 35 行，且其反模式清单会直接否决我们要采纳的视觉方向 |
| `.cursor/rules/axiom-street.mdc` | §Current scope 指向本文；§UI 第 66–67 行改为允许深色主题但保留"禁紫渐变/霓虹/玻璃拟态/机器人图标"；L18 mock 规则**加强**为"仓库内不得存在合成回测数据的模块"（这条正是被违反的那条） |

### 4.4 验收

- `grep -rn "ROADMAP" .` 只在 git 历史里有命中
- 「当前阶段」在整个仓库只声明一次
- 8 个闸门的判定口径能在 `validation-gates.md` 一处读全

---

## 5. W1 — 垃圾代码清除（2–3 天）

全部条目均已用 `grep` 逐一验证，非推测。

### 5.1 `apps/terminal` 整体删除 —— 最大单笔

```
删除：apps/terminal/**          44 个受版本控制文件 / 4,403 行
      ├─ mocks/                  959 行  合成回测数据（违反铁律 L18）
      ├─ components/           1,711 行  含 copilot.tsx 266 行（违反铁律 L14）
      ├─ pages/                1,203 行
      └─ lib/prng.ts              43 行  mulberry32 + Box–Muller
顺带回收磁盘：node_modules 160M + dist 988K
```

**删除前必须先完成 6.1 的令牌收割**，否则视觉资产随代码一起丢失。这是 W1 与 W3a 之间唯一的顺序耦合。

`apps/terminal/public/logo.png` 与 `brand/logo.png` 是同一个 405,353 字节文件的两份拷贝——删 terminal 那份，`brand/` 保留为唯一来源。

### 5.2 `quant/risk/` 删除

`grep -rn "quant\.risk\|RiskEngine"` 在 `quant/risk/` 之外**零命中**。它定义了 `RiskEngine` ABC 与 `PassThroughRiskEngine`。

`PassThroughRiskEngine` 尤其危险：**一个默认放行的风控引擎，正是"静默降级"这个最高优先级反模式的教科书形态**。它现在没被引用所以无害，但它一旦被谁 import 上就是灾难。

处置：整个包删除。`Risk ⊥ everything` 这条边界已经写在 `architecture.md` §1，不需要一个空 ABC 来重复声明。Phase 6 落地真实风控时重建——那时的接口形状会由真实需求决定，不由今天的猜测决定。

### 5.3 `packages/shared-types/` 删除

整个 `packages/` 目录只有 `index.ts` 一个文件，`grep` 零引用。前端在 `lib/api.ts` 里手工维护 18 个 interface，与 `services/api/schemas.py`（489 行）重复。

处置：删除 `packages/`。类型重复问题由 6.3 的 OpenAPI codegen 解决——那是真正的修复，`shared-types` 只是一个从未被接线的意图。

### 5.4 `quant/data/duckdb_query.py` 删除

唯一引用者是 `tests/unit/test_lean_converter.py`。API 与 worker 都不用。但 DuckDB 同时被列在 `pyproject.toml` 依赖与 `architecture.md` §5 技术选型表——**文档在宣称一个没有接线的能力**。

处置：删模块 + 删依赖 + 删技术选型表那一行。Phase 8 的因子回归如果真需要列式扫描，那时按真实需求重新引入。

### 5.5 前端未使用依赖

`@tanstack/react-table` 与 `date-fns` 在 `apps/web/src` 里 **0 文件命中**。`ROADMAP.md` §6.5 早就标记过，一直没清。处置：`npm uninstall` 两个。

### 5.6 SPY 时代的命名残留

Phase 2 已把管线参数化，但命名层没跟上：

| 对象 | 现状 | 目标 |
|------|------|------|
| `quant/data/ingest_spy.py`（666 行） | 模块名写死 SPY，内含通用 `ingest()` / `load_symbol_parquet()` | 重命名为 `quant/data/ingest/`（拆分见 6.2）。**56 处 `quant.data.ingest_spy` 路径引用**散在代码、Makefile、README、docs——机械但面广，一次改完 |
| `ingest_spy()`、`load_spy_parquet()` | 兼容 shim | 删除；调用点改走通用函数 |
| `fetch_spy_daily`、`convert_spy_to_lean`、`ensure_lean_spy_data` | 仍存在 | 逐个确认是否已有通用版本，删除 shim |

### 5.7 磁盘与仓库卫生

| 项 | 现状 | 处置 |
|----|------|------|
| `jobs/` | 7.5M / 14 个任务目录，**无任何保留策略**。已有 `prune_snapshots` 管数据快照，但 jobs 只增不减 | 新增 `services/api/prune_jobs.py` + Makefile target：保留 golden + 最近 N 次，其余删除 |
| `jobs/spy-200dma-smoke{,2,3}` | 2026-08-28 手工 smoke 遗留，已被 `jobs/golden/` 取代 | 删除 |
| `data/corporate_actions/SPY.parquet` | **受版本控制的二进制行情数据**。`.gitignore` 忽略了 `data/market/**/*.parquet` 却漏了 `corporate_actions/` | 补 `.gitignore` 规则 + `git rm --cached`。两类 vendor parquet 应同等处理 |
| `apps/web/.next` 173M、`.mypy_cache` 77M | 已 gitignore，纯本地 | 加 `make clean` |

### 5.8 W1 验收

- `ruff check` + `mypy quant services` + `pytest tests/unit -q` 全绿（349 个测试不允许减少）
- `npx tsc --noEmit` + `npm test` 全绿
- `npm run build` 成功
- golden test 通过（`make golden`）——本包不碰引擎/数据/指标，golden 数字**必须逐点不变**
- 净删除 ≥ 4,600 行

---

## 6. W2 — 架构整理（1.5–2 周）

### 6.1 核心问题：七份复制粘贴

这是整个仓库最大的结构债。7 类验证检验，每一类在**三个地方**各有一份近乎相同的实现：

| 层 | 文件 | 行数 | 重复形态 |
|----|------|------|---------|
| API | `services/api/services/validation.py` | **1,161** | 7 × (`_enqueue_X` + `create_X_run`)，每对 ~80–110 行同构 |
| Worker | `services/worker/tasks.py` | **1,336** | 7 × (`execute_X_scan` + `@celery_app.task run_X_task`) |
| Web | `features/validation/*-form.tsx` + `experiments/pbo-scan-form.tsx` | **892** / 7 文件 | 7 个表单全部 `useState` + `api.` + `toast` 同一形状 |

合计约 **3,389 行**，其中真正独特的逻辑（各检验的参数与判定口径）已经在 `quant/validation/*.py` 里了。这三层是纯粹的传递样板。

### 6.2 目标形态：单一 `ValidationSpec` 注册表

一个检验类型 = 一份声明：

```
ValidationSpec
├─ kind              WALK_FORWARD | DSR | PBO | SENSITIVITY | COST | BOOTSTRAP | REGIME | SPA
├─ params_schema     Pydantic model（前端表单由它生成）
├─ step_count(params)  进度条步数
├─ runner            quant/validation/ 里的纯函数入口
├─ gate              判定规则（口径来自 docs/validation-gates.md）
└─ auto_on_backtest  bool（bootstrap / regime 为真，SPA 必须为假）
```

三层各自收敛为一份通用实现：

```
services/api/services/validation.py   1,161 → ~350   （通用 create_run + 注册表）
services/worker/tasks/                1,336 → ~450   （拆包 + 通用 execute_run）
  ├─ backtests.py         回测执行 / 取消 / 孤儿回收
  ├─ validation.py        通用 runner + 扫描并行
  └─ data.py              摄取 / 对账 Beat
features/validation/                    892 → ~250   （单一 spec 驱动表单，见 7.2）
```

预计净减 **~2,100 行**，且新增第 9 个检验从"改三个文件 ~250 行"变成"加一份 spec"。

**风险控制**：本包会重排闸门代码路径，而闸门是产品护城河。要求：
- `tests/unit/test_validation_pipeline.py`（故意过拟合策略必须 PBO > 0.5、DSR 过不了 95% 线、客户端 PATCH `VALIDATED` 仍 409）在重构**前后逐字节相同的断言下**通过；
- 7 个 `test_execute_*.py` 全部保留，不允许因为"新架构不好测"而删改；
- 先写注册表并让**一个**检验（`bootstrap`，最简单且已有自动写入路径）走通，再迁其余六个。不做一次性大爆炸重写。

### 6.3 `quant/data/ingest_spy.py` 拆分（666 行 → 4 模块）

单个文件承担 8 项职责：拉取编排、增量合并、restatement 检测、快照发布、质量报告聚合、快照裁剪、CLI、状态查询。

```
quant/data/ingest/
├─ __init__.py      ingest() 编排入口 + 公共类型
├─ snapshot.py      _publish_latest / latest_snapshot_dir / prune_unreferenced_snapshots
├─ incremental.py   _prior_parquet_path / _merge_incremental / _detect_restatements
└─ cli.py           __main__ 入口（--symbols-file / --mode / --provider / --reconcile-with）
```

与 5.6 的重命名合并成一次改动，避免两次触碰 56 个引用点。

### 6.4 其余架构项

| 项 | 处置 |
|----|------|
| `settings/page.tsx` 411 行 | 逻辑移入 `features/settings/settings-desk.tsx`，路由文件回归 ≤ 15 行，与其余 13 个 `page.tsx` 一致 |
| 边界复核 | `quant/` 零 web framework import 已验证通过，**加一个测试锁死它**（import 扫描），防止回归 |
| `packages/` | W1 删空后，作为 6.5 OpenAPI codegen 的产物目录重建，或彻底不要（倾向后者：codegen 产物放 `apps/web/src/lib/api-types.gen.ts` 更近） |

### 6.5 类型单一来源（OpenAPI codegen）

`lib/api.ts` 685 行手工维护 18 个 interface，镜像 `schemas.py` 489 行。这是**两份会静默漂移的真值**——后端改字段，前端只会在运行时炸。

处置：`openapi-typescript` 从 `/openapi.json` 生成类型，`api.ts` 只保留 fetch 封装与错误处理。CI 加一步：生成后 `git diff --exit-code`，漂移即失败。

---

## 7. W3 — 前端 UI v2（2–3 周）

W3a（令牌与主题）不依赖 W2，可并行；W3b（表单收敛）必须在 W2 之后。

### 7.1 W3a — design system v2：收割 terminal 的视觉工程

`apps/terminal` 的令牌体系比 `apps/web` 成熟得多。**收割结构，不收割配色。**

| 收割 | terminal 的值 | web 现状 | v2 决定 |
|------|--------------|---------|--------|
| **表面层级** | 5 级：`bg / sunken / panel / raised / overlay` | 2 级：`bg / bg-secondary` | **采纳 5 级**。这是"面板密集型终端"观感的真正来源，比任何配色都重要 |
| **发丝边框** | `rgba(255,255,255,0.065)` + `0.13` 两档 | 单一 `rgba(15,23,42,0.08)` | **采纳两档**（结构线 / 强调线），做浅色等价值 |
| **密度** | 13px / 1.45 行高 / `overflow:hidden` 外框 + 内部滚动区 | 默认 14–16px，整页滚动 | **采纳**。财务终端的信息密度是可信度的一部分 |
| **数字字体** | JetBrains Mono Variable | Inter + `tabular-nums` | **采纳等宽**用于所有财务数字。`tabular-nums` 只对齐，等宽同时传递"这是数据不是文案" |
| **圆角** | 5 / 7 / 10px 三档 | 单一 12px | **采纳三档**。12px 偏消费级；MASTER.md 需同步改 |
| **涨跌语义色** | 去饱和 `#3fa97c` / `#d9635e` | 高饱和 `#12B76A` / `#F04438` | **采纳去饱和**。这与 VISION 信念六「克制的红绿」一致——现值偏赌场 |
| **强调色预算** | < 5% 面积 | 未定义 | **采纳预算约束**，写进 MASTER.md |
| **强调色本身** | 琥珀 `#e3b341` | `#1677FF` | **拒绝琥珀，保留 `#1677FF`**（见下） |

**为什么拒绝琥珀**：琥珀+近黑是 Bloomberg / OpenBB 的签名，不是 Axiom 的。`VISION.md` 信念六点名 `#1677FF` 为单一主色，这是品牌一致性问题而非审美问题。深色主题下把 `#1677FF` 提亮到 `#4d94ff` 量级即可保证对比度。**一个品牌一个强调色，两个主题共用。**

其余 W3a 工作：

- **双主题**：`:root` 定义浅色全量令牌 → `@media (prefers-color-scheme: dark)` 与 `[data-theme]` 各覆盖一遍，颜色不允许只在 media query 内定义
- **消灭 34 处硬编码 hex**（12 文件，图表层为主）。图表尤其重要：Lightweight Charts 的配色目前写死，深色主题下会直接不可读
- **重写 `MASTER.md`**：35 行 → 完整 v2 令牌表 + 双主题规则 + 更新反模式清单（保留禁紫渐变/霓虹/玻璃拟态/机器人图标；删除"禁 cyberpunk black"，改为"禁纯 `#000`，近黑起于 `#0a0a0b`"）
- **加载态一致性**：`EmptyState` 用在 11 个文件、`Skeleton` 只用在 1 个。11 个页面有诚实空态但没有加载骨架——补齐

### 7.2 W3b — 表单收敛（依赖 W2）

7 个验证表单 892 行 → 单一 `<ValidationRunForm spec={...}>` ~250 行，字段由 W2 的 `params_schema` 经 OpenAPI 类型生成。`/experiments` 的 PBO 表单并入同一组件（它与 `/validation` 的六个是同构的，只因为放在不同路由就复制了一遍）。

### 7.3 W3c — i18n 抽取（D3 落地）

中文文案硬编码在组件里（`nav.ts` 的 11 个标签、各页面标题与说明）。抽成 `apps/web/src/locales/zh-CN.ts`，预留 `en.ts` 空壳。**现在做的成本最低**——页面数只会增加。

### 7.4 W3d — 前端测试（最重要的一项）

9,133 行 UI / 18 个测试 / 0 组件测试 / 0 E2E。这是整个项目最大的质量缺口，与后端 349 个测试形成刺眼对比。

| 层 | 目标 |
|----|------|
| 组件单测（Vitest + Testing Library） | 优先 `MetricTile`（数字格式与正负色）、`ValidationRunForm`（参数校验与提交）、`truth-strip`（DSR/PBO 必须排在原始 Sharpe 之前——这是产品承诺，必须有测试锁死） |
| E2E（Playwright） | 3 条关键路径：① 建策略 → 跑回测 → 看 tearsheet；② 发起验证 → 闸门失败 → `VALIDATED` 不可达；③ 摄取数据 → 质量报告可见 |
| CI | 两者接入 `.github/workflows/ci.yml` 的 `web` job |

第 ② 条 E2E 尤其关键：**"未通过验证的策略在 UI 上无法被标记为 VALIDATED"是产品的核心承诺，目前只有后端 409 测试，没有任何 UI 层证据。**

### 7.5 W3 验收

- 深浅双主题下 11 个页面均可读，图表含在内
- `grep -rn "#[0-9a-fA-F]\{6\}" apps/web/src --include='*.tsx'` 零命中（令牌之外）
- 前端测试 ≥ 60 个 + 3 条 E2E 绿
- 无中文硬编码在组件内
- 单个组件文件 ≤ 400 行

---

## 8. 后续功能路线

### 8.1 W4 — Phase 4 收尾（1 周）

Phase 4 已约 90%。剩余项（`ROADMAP.md` §6 的真实缺口，已剔除它误报为"未做"的 round-trip 配对）：

| 项 | 现状 |
|----|------|
| 多回测对比 | 当前只能叠加**同策略**第二条曲线。需要跨策略、≥3 条 + 对比表 |
| OpenAPI codegen | 归入 W2 §6.5 |
| Playwright E2E | 归入 W3 §7.4 |
| MAE/MFE 与持仓周期分布 | round-trip 数据已在库（`holding_period` 已解析），只缺可视化 |

### 8.2 Phase 5 — AI Copilot（4–5 周）

**前置条件（不可跳过）**：W0–W4 全部关闭。理由不是流程洁癖——`.cursor/rules` L14 的顺序约束存在的原因是 AI 会以人类无法企及的速度批量生产过拟合策略，而 W2 之前的验证代码路径正在被重排，闸门在重构中期是最脆弱的。

五条不可妥协的约束（源自 `VISION.md` 信念四，不变）：AI 不得改风控限额 / 不得改验证状态 / 生成策略走完整验证无快速通道 / 每次试验写入试验台账 / 无真实能力不上聊天框。

**可从 `apps/terminal` 抢救的设计**：`copilot.tsx` 的**交互形态**（右侧常驻上下文面板，感知当前页面与策略版本）是合理的产品设计，值得在删除前记录下来。删掉的是它背后照本宣科的假回答，不是这个壳的布局思路。

最有价值的功能仍是**劝用户停下来**：「你已在此数据快照上试了 47 次，继续搜索的多重检验惩罚已很重」——试验台账已经有这个数字，这是最容易实现也最诚实的一条。

### 8.3 Phase 6 / 7 — Paper 与 Live

| 前置项 | 说明 |
|--------|------|
| **风控引擎实体化** | W1 已删掉装饰性 stub。此处从零实现：单标的仓位上限、组合杠杆上限、日内亏损熔断、回撤熔断、集中度、订单速率。链路 `Strategy → Risk → Execution → Broker` |
| **认证与多用户** | D2 的降级在此到期。Live 涉及真实资金，`actor="local"` 的审计日志不可接受 |
| **容器加固** | seccomp profile、只读根文件系统、非 root、危险 import 静态检查。用户提交的任意 Python 在容器内执行，目前仅靠 `--network none` + 资源限制 |
| **回测–实盘对账** | **北极星指标的唯一实现方式**，不是加分项 |

### 8.4 Phase 8 — 组合与归因

多策略相关性与组合构建（等权 / 风险平价 / 均值方差 / HRP）、组合层回撤归因、**Fama-French 三/五因子 + 动量回归**（回答"这是真 alpha 还是 beta 伪装"）、Brinson 归因。

若此处确需列式扫描，重新引入 DuckDB（W1 §5.4 删除的理由是"未接线"，不是"不该用"）。

### 8.5 贯穿性工程债

| 项 | 触发时机 |
|----|---------|
| `jobs/` 保留策略 | W1 §5.7，已排入 |
| 可观测性：Prometheus（回测时长/失败率/队列深度）+ Sentry + OTel | Phase 5 之前。AI 批量试验会让队列深度第一次真正成为问题 |
| Docker stdout/stderr 经 API 可读 | 现在只落 `jobs/{id}/docker_*.log`，排障要 ssh 进容器 |
| 默认口令 `street:street` | 已提交在 `docker-compose.yml` 与 `alembic.ini`。D2 下风险可控，但改成环境变量注入是 10 分钟的事 |
| CORS `allow_credentials: true` 宽松配置 | 与认证一同处理 |

---

## 9. 里程碑

| 里程碑 | 内容 | 累计 | 完成后的能力 |
|--------|------|------|-------------|
| **N0** | W0 文档融合 | 1 天 | 单一计划来源，零矛盾声明 |
| **N1** | W1 垃圾清除 | ~4 天 | 净删 ≥4,600 行；仓库内不存在合成回测数据 |
| **N2** | W2 架构整理 | ~2.5 周 | 净减 ~2,100 行；新增检验从 250 行变一份 spec |
| **N3** | W3 UI v2 | ~5 周 | 双主题、令牌统一、前端测试从 18 → 60+ 与 3 条 E2E |
| **N4** | W4 Phase 4 收尾 | ~6 周 | Phase 4 关闭，可以开 Phase 5 |
| **N5** | Phase 5 AI Copilot | ~11 周 | AI 加速研究（受闸门约束） |
| **N6** | Phase 6/7 Paper + Live | ~20 周 | 研究到执行闭环 + 回测实盘对账（北极星可测） |
| **N7** | Phase 8 组合归因 | ~24 周 | 多策略组合与真 alpha 判定 |

**如果只能做三件事**：N1（删掉自相矛盾的部分）、N3d（前端测试——目前唯一没有安全网的 9,133 行）、N6 的回测–实盘对账（唯一能验证北极星的功能）。

---

## 10. 施工纪律的三处修订

`.cursor/rules/axiom-street.mdc` 需要跟随本计划调整。前两条是**加强**，不是放松：

1. **L18 mock 规则加强**：现文「Mock data 只许用于空态 / Storybook」被违反了，因为它约束的是"用途"，而用途可以事后辩解。改为约束"存在"：**仓库内不得存在合成回测数据的模块**（合成价格序列、合成指标、合成成交）。这条可以被 `grep` 检查，前一条不能。

2. **新增：单一真值声明**。「当前阶段」「已交付能力」在整个仓库只允许声明一处。本次审计发现三处互相矛盾的阶段声明，根因是没有这条规则。

3. **L66–67 UI 规则修订**：允许深色主题（近黑起于 `#0a0a0b`，禁纯 `#000`），保留禁紫渐变/霓虹/玻璃拟态/机器人图标，新增强调色面积预算 < 5%、财务数字用等宽。

---

## 附录 A：本次审计的量化基线

复核这份计划的执行效果时，对照下表。

| 指标 | 2026-09-04 | W4 完成目标 |
|------|-----------|------------|
| 受版本控制文件 | 304 | ~250 |
| Python 行数（`quant` + `services`） | 14,797 | ~12,700 |
| 前端行数（`apps/web/src`） | 9,133 | ~8,500（收敛与删除抵消新增测试） |
| 第二前端行数（`apps/terminal/src`） | 4,403 | 0 |
| Python 测试 | 349 / 51 文件 | ≥ 349（不允许减少） |
| 前端测试 | 18 / 4 文件 | ≥ 60 + 3 E2E |
| 最大单文件（Python） | `worker/tasks.py` 1,336 | ≤ 500 |
| 次大单文件（Python） | `api/services/validation.py` 1,161 | ≤ 400 |
| 最大单文件（前端） | `validation-desk.tsx` 668 | ≤ 400 |
| 硬编码 hex（`apps/web/src`） | 34 处 / 12 文件 | 0 |
| 未使用 npm 依赖 | 2 | 0 |
| 死模块 | 3（`quant/risk`、`packages/shared-types`、`duckdb_query`） | 0 |
| 计划文档 | 7 份 / ~1,390 行 | 5 份 |
| 阶段声明来源 | 3 处（互相矛盾） | 1 处 |
| API 端点 / 路由文件 | 60 / 9 | 不变 |
| Alembic migration | 9 | 随 schema 变更 |

## 附录 B：关键文献

统计验证的实现以原始文献为准，不凭记忆推导公式。

- Bailey, D. & López de Prado, M. (2014). *The Deflated Sharpe Ratio.*
- Bailey, D., Borwein, J., López de Prado, M. & Zhu, Q. (2015). *The Probability of Backtest Overfitting.*
- Bailey, D. et al. (2014). *Pseudo-Mathematics and Financial Charlatanism.*（含 Minimum Backtest Length）
- White, H. (2000). *A Reality Check for Data Snooping.*
- Hansen, P. R. (2005). *A Test for Superior Predictive Ability.*
- Politis, D. & Romano, J. (1994). *The Stationary Bootstrap.*
- Politis, D. & White, H. (2004). *Automatic Block-Length Selection.*
- López de Prado, M. (2018). *Advances in Financial Machine Learning.*（CSCV、组合构建、HRP）
