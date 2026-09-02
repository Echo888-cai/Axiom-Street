# 市场数据源

## 当前（Phase 2）

无需 API key 即可跑通摄取。

| 优先级 | 数据源 | Key | 能力 |
|--------|--------|-----|------|
| 1 | Yahoo Finance (`yfinance`) | — | OHLCV + 分红 + 拆分 |
| 2 | Stooq | — | 仅 OHLCV，**不提供分红/拆分** |

Stooq 不声明 `dividends`/`splits`。能力不足时摄取与 Adjusted 回测**直接失败**，不会生成空 factor file 冒充已调整价格。

Polygon 对账源尚未接线（`wired: false`）。接入后 yfinance 降为交叉校验源。

## 摄取模式

| mode | 行为 |
|------|------|
| `full`（默认） | 按 `start`/`end` 全量拉取，写入**新的**不可变快照 |
| `incremental` | 要求已有 prior bars；仅从每个标的最后一根 K 线的次日开始拉取，与历史拼接后写入**新快照** |

规则：

- 摄取**永不原地改写**旧快照；历史通过 `superseded_by` 链保留。
- 增量路径若发现重叠日期的 close / 分红 / 拆分被 vendor 改写，写入 `vendor_restatement` **warning**（不静默吞掉），仍产出新快照。
- 无 prior 时调用 `incremental` → **直接报错**，要求先跑一次 `full`。

```bash
python -m quant.data.ingest_spy SPY
python -m quant.data.ingest_spy SPY QQQ --mode incremental
# 或 POST /api/v1/data/ingest
#   {"symbols": ["SPY", "QQQ"], "mode": "incremental"}
```

环境变量前缀为 `STREET_`（见 `.env.example`）。

磁盘布局：

- 不可变快照：`data/snapshots/{slug}-daily-{YYYYMMDD}-{hash6}/`
- 兼容路径 `data/market/`、`data/lean/`、`data/manifest.json` 指向 latest 快照
- 每个标的：`market/equities/US/daily/{SYM}.parquet` 与 `lean/equity/usa/daily/{sym}.zip`

## 可选 key（暂未接线）

Phase 2 后续会把 Polygon 接为主源、yfinance 降为对账源。在那之前这些 key 标为 `wired: false`。

```bash
POLYGON_API_KEY=
ALPACA_API_KEY=
ALPACA_API_SECRET=
ALPACA_PAPER=true
ALPHA_VANTAGE_API_KEY=
TIINGO_API_KEY=
```
