# 市场数据源

## 当前（Phase 2 WP-1）

无需 API key。

| 优先级 | 数据源 | Key | 能力 |
|--------|--------|-----|------|
| 1 | Yahoo Finance (`yfinance`) | — | OHLCV + 分红 + 拆分 |
| 2 | Stooq | — | 仅 OHLCV，**不提供分红/拆分** |

Stooq 不声明 `dividends`/`splits`。能力不足时摄取与 Adjusted 回测**直接失败**，不会生成空 factor file 冒充已调整价格。

## 摄取

```bash
python -m quant.data.ingest_spy SPY
python -m quant.data.ingest_spy SPY QQQ
# 或 POST /api/v1/data/ingest  {"symbols": ["SPY", "QQQ"]}
# 或 Settings 页填写标的后点「拉取行情」
```

磁盘布局：

- 不可变快照：`data/snapshots/{slug}-daily-{YYYYMMDD}-{hash6}/`
- 兼容路径 `data/market/`、`data/lean/`、`data/manifest.json` 指向 latest 快照
- 每个标的：`market/equities/US/daily/{SYM}.parquet` 与 `lean/equity/usa/daily/{sym}.zip`

重新摄取**不覆盖**旧快照，只把旧记录的 `superseded_by` 指向新快照。

## 可选 key（暂未接线）

Phase 2 WP-3 会把 Polygon 接为主源、yfinance 降为对账源。在那之前这些 key 标为 `wired: false`。

```bash
POLYGON_API_KEY=
ALPACA_API_KEY=
ALPACA_API_SECRET=
ALPACA_PAPER=true
ALPHA_VANTAGE_API_KEY=
TIINGO_API_KEY=
```
