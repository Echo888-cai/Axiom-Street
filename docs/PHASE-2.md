# Phase 2 — 数据平台化与多资产（当前阶段）

> **目标：从「只能跑 SPY」到「能跑任意标的池」，并具备机构级数据血缘。**
> 预估 4–5 周 / 4 个工作包。
> 前置：Phase 1.5 已关闭（见 `docs/PHASE-1.5.md`）。

**这个阶段不加验证引擎、不加 AI。** 生存者偏差和不可复现的多标的回测，会把错误数字放大 N 倍。

按顺序执行。WP-1 是后续 universe / 对账 / 增量摄取的地基。

---

## WP-1 · 解除 SPY 硬编码

**核心决策**：摄取、转换、引擎一律按 `symbols: list[str]` 工作。SPY 只是默认值，不是架构假设。

### 任务

- [x] `fetch_daily(symbol)`；`fetch_spy_daily()` 保留为薄封装
- [x] `ingest(symbols)` 写入 `data/snapshots/{slug}-daily-{date}-{hash}/`，每个标的一份 parquet
- [x] `convert_to_lean(symbols)` 生成 `{symbol}.zip` / factor / map / symbol-properties 行
- [x] `BacktestRequest.universe`；LEAN 按请求的标的挂载数据
- [x] DuckDB 为每个 parquet 注册 `{symbol}_daily` 视图
- [x] `POST /api/v1/data/ingest` 接受 `symbols`；`/ingest/spy` 保留为别名
- [x] Settings 页可填写逗号分隔标的
- [ ] 一条命令摄取 2+ 标的后，能跑一个非 SPY 的日线策略（本机确认）

### 验收

- 摄取 `SPY,QQQ` 产生两个 parquet 与两个 LEAN zip，旧 SPY 快照仍在
- 缺 parquet 的标的让回测失败，错误指向缺失文件，不静默跳过
- `ingest_spy()` 行为与 Phase 1.5 兼容

---

## WP-2 · 标的池（Universe）作为一等实体

新增 `universes` + `universe_members`，支持静态列表与**时点正确**的成分变动（`effective_from` / `effective_to`）。

静态 `20000101,spy` map file 无法表达退市。不做这一点，多股票回测会系统性偏高。

### 任务

- [x] `universes` / `universe_members` 表 + Alembic migration
- [x] 成员必须带 `effective_from` / `effective_to`（退市标的 `effective_to` 非空）
- [x] 回测按 `[start, end]` 展开为时点正确的成分，而不是快照里的静态列表
- [x] API：CRUD universe；创建回测可引用 `universe_id`
- [x] 前端：标的池管理页（诚实空态，不用假成分）

### 验收

- 摄取一支已退市股票，其 `effective_to` 被正确记录
- 用含退市成分的 universe 跑回测，退市日后不再出现该标的

---

## WP-3 · 数据源升级与交叉对账

- [ ] Polygon adapter（`.env` 已预留 key）作为主源
- [ ] yfinance 降级为对账源，不再是唯一生产路径
- [ ] 双源 close 偏差 > 10 bps 标记 suspect，进入 quality report（fail-closed 或显式警告，不得静默）
- [ ] 分红/拆分必须双源一致才写入 factor file

### 验收

- 对账报告能指出至少一个 yfinance 与 Polygon 不一致的历史 bar
- Polygon 不可用时回测失败并说明，不静默回到无分红源

---

## WP-4 · 增量摄取

当前每次全量重拉。改为按日期增量 append + 定期全量校验（检测 vendor restatement）。

restatement **必须产生新快照**，不得原地修改。

### 验收

- 能一条命令摄取 500 支股票日线并生成对应 LEAN 数据
- 能跑一个 10 标的的横截面策略回测
- vendor restatement 后旧快照仍可读，新回测默认用新快照

---

## 阶段验收

- [ ] WP-1 到 WP-4 全部完成并有回归测试
- [ ] 多标的快照内容寻址、不可变
- [ ] 时点正确的 universe 可防止生存者偏差
- [ ] 没有任何新增的静默失败路径

完成后才能进入 Phase 3（统计验证）。
