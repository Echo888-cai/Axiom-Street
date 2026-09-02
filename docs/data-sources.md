# 市场数据源

## 当前（Phase 2）

| 优先级 | 数据源 | Key | 能力 | 状态 |
|--------|--------|-----|------|------|
| 1 | Yahoo Finance (`yfinance`) | — | OHLCV + 分红 + 拆分 | 默认主路径 |
| 2 | Stooq | — | 仅 OHLCV | auto 回退；无分红时 fail loud |
| 3 | Polygon | `POLYGON_API_KEY` | OHLCV + 分红 + 拆分 | **已接线**；无 key 时显式失败 |

Stooq 不声明 `dividends`/`splits`。能力不足时摄取与 Adjusted 回测**直接失败**。

## 摄取模式

| mode | 行为 |
|------|------|
| `full`（默认） | 按 `start`/`end` 全量拉取，写入**新的**不可变快照 |
| `incremental` | 要求已有 prior bars；仅从最后一根 K 线次日拉取并拼接 |

## 双源对账

```bash
# Polygon 为主、yfinance 为对账源（需 POLYGON_API_KEY）
python -m quant.data.ingest_spy SPY --provider polygon --reconcile-with yfinance
```

| 检查 | 阈值 | 严重度 |
|------|------|--------|
| Close 偏差 | > 10 bps | `warning`（suspect bar） |
| 分红 / 拆分不一致 | 任一事件冲突 | `blocking`（拒绝写入） |

也可设 `STREET_RECONCILE_WITH=yfinance`。

规则：

- 摄取**永不原地改写**旧快照
- 增量路径发现 vendor restatement → `vendor_restatement` warning + 新快照
- 无 prior 时 `incremental` → fail loud
- Polygon 无 key → fail loud（不静默降级到 yfinance）

```bash
python -m quant.data.ingest_spy SPY
python -m quant.data.ingest_spy SPY QQQ --mode incremental
# POST /api/v1/data/ingest
#   {"symbols": ["SPY"], "provider": "polygon", "reconcile_with": "yfinance"}
```

环境变量前缀为 `STREET_`（见 `.env.example`）。

磁盘布局：

- 不可变快照：`data/snapshots/{slug}-daily-{YYYYMMDD}-{hash6}/`
- 兼容路径 `data/market/`、`data/lean/`、`data/manifest.json` 指向 latest 快照

## 可选 key

```bash
POLYGON_API_KEY=
STREET_RECONCILE_WITH=
ALPACA_API_KEY=
ALPACA_API_SECRET=
ALPACA_PAPER=true
ALPHA_VANTAGE_API_KEY=
TIINGO_API_KEY=
```
