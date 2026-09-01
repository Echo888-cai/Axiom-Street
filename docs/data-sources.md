# 市场数据源

## 当前（Phase 1 / 1.5）

无需 API key。

| 优先级 | 数据源 | Key | 能力 |
|--------|--------|-----|------|
| 1 | Yahoo Finance (`yfinance`) | — | OHLCV + 分红 + 拆分 |
| 2 | Stooq | — | 仅 OHLCV，**不提供分红/拆分** |

### ⚠️ Stooq 降级是当前最危险的缺陷（P0-5）

yfinance 失败时代码会自动降级到 Stooq。但 Stooq 不提供 corporate actions，`_normalize()` 会填入 `dividends=0, splits=0`，导致：

```
无分红事件 → factor file 只有终止行 20501231,1,1,0
           → 但策略仍用 DataNormalizationMode.Adjusted
           → LEAN 拿到未调整价格却以为是已调整的
           → 回测结果错误，全程无任何警告
```

SPY 年化分红约 1.5%，十年回测累计误差可达 15% 以上。

**Phase 1.5 WP-3 的修复方向**：数据源声明 `ProviderCapabilities`，能力不足时**让回测直接失败**，而不是静默降级。详见 `docs/PHASE-1.5.md` WP-3。

在该修复完成前，若 `manifest.json` 的 `source` 显示为 `stooq`，请重新用 yfinance 摄取后再跑回测。

## 摄取

```bash
python -m quant.data.ingest_spy
# 或 POST /api/v1/data/ingest/spy
# 或 Settings → 摄取 SPY
```

规范化存储：`data/market/equities/US/daily/SPY.parquet`
LEAN 转换产物：`data/lean/equity/usa/daily/spy.zip`
完整性：`data/manifest.json`（SHA256）

**注意**：当前摄取是覆盖式的——重新摄取会覆盖 parquet 与 manifest，使历史回测记录的 `data_version` 指向不存在的数据。Phase 1.5 WP-4 会改为不可变快照 `data/snapshots/{snapshot_key}/`。

## 可选 key（暂未接线）

按需写入 `.env`：

```bash
# Phase 2 数据平台化：作为主源，yfinance 降级为对账源
POLYGON_API_KEY=

# Phase 6 模拟盘
ALPACA_API_KEY=
ALPACA_API_SECRET=
ALPACA_PAPER=true

ALPHA_VANTAGE_API_KEY=
TIINGO_API_KEY=
```

`provider_status()` 会把这些标为 `wired: false`——adapter 尚未实现。

## Phase 2 的数据源目标

- Polygon 作为主源，yfinance 降级为**交叉对账源**（同日 close 偏差超过 10 bps 则标记该 bar 为 suspect）
- 分红/拆分事件需双源一致才写入 factor file
- 增量摄取 + 定期全量校验（检测 vendor restatement，restatement 必须产生新快照）
- 时点正确的标的池成分历史，消除生存者偏差

详见 `docs/ROADMAP.md` 第 4 章。

## 回测运行时

LEAN 在 Docker 中运行。没有 Docker Desktop 时摄取仍可用，但无法执行回测。

**当前限制**：`docker compose up` 起栈后点击回测会失败——`docker.sock` 没有挂给 API 容器，而回测目前是在 API 进程内的线程里跑的。Phase 1.5 WP-6 收敛到 Celery 后修复。
