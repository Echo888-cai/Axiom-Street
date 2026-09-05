# 市场数据源

## 当前（Phase 2 已关闭）

| 优先级 | 数据源 | Key | 能力 | 状态 |
|--------|--------|-----|------|------|
| 1 | Polygon | `POLYGON_API_KEY` | OHLCV + 分红 + 拆分 + 股本/SIC | **有 key 时默认主源**；无 key 显式失败 |
| 2 | Yahoo Finance (`yfinance`) | — | OHLCV + 分红 + 拆分 + 股本/GICS | 无 Polygon key 时的默认主路径；有 key 时作对账源 |
| 3 | Stooq | — | 仅 OHLCV | auto 回退；无分红时 fail loud |

Stooq 不声明 `dividends`/`splits`。能力不足时摄取与 Adjusted 回测**直接失败**。

基本面：股本按 filing/vendor as-of 正向填充；板块/行业只从分类拉取日生效。**不会**用当前市值回填历史。

## 摄取模式

| mode | 行为 |
|------|------|
| `full`（默认） | 按 `start`/`end` 全量拉取，写入**新的**不可变快照 |
| `incremental` | 要求已有 prior bars；仅从最后一根 K 线次日拉取并拼接 |

## 双源对账

```bash
# 有 POLYGON_API_KEY 时 auto = Polygon 主源 + yfinance 对账
python -m quant.data.ingest.cli SPY
# 显式指定
python -m quant.data.ingest.cli SPY --provider polygon --reconcile-with yfinance
```

| 检查 | 阈值 | 严重度 |
|------|------|--------|
| Close 偏差 | > 10 bps | `warning`（suspect bar） |
| 分红 / 拆分不一致 | 任一事件冲突 | `blocking`（拒绝写入） |

也可设 `STREET_RECONCILE_WITH=yfinance`。

## 定期全量校验

Celery Beat 每天对当前已发布 universe 做一次 `mode=full` 再拉（任务名 `data.reconcile_market`），用来抓 vendor 事后改历史。发现重叠日期 close / 分红 / 拆分变化 → `vendor_restatement` warning，并写入**新快照**；旧快照只会被 `superseded_by` 标记。

| 变量 | 默认 | 作用 |
|------|------|------|
| `STREET_MARKET_RECONCILE_ENABLED` | `true` | 关闭则 Beat 跳过；手动 `POST /api/v1/data/reconcile` 仍可用 |
| `STREET_MARKET_RECONCILE_INTERVAL_SECONDS` | `86400` | Beat 间隔（下限 60s） |
| `STREET_MARKET_RECONCILE_PROVIDER` | `auto` | 全量再拉的主源 |
| `STREET_MARKET_RECONCILE_WITH` | 空 | 可选对账源，例如 `yfinance` |

已有 ingest 在跑时，定时任务会 skip（`ingest_in_progress`），避免并发写。Settings 可手动触发同一路径。

## 吞吐与限速

一条命令拉 500 只日线（含 LEAN zip）是 Phase 2 验收目标。出站请求**不会**无节流狂轰 vendor。

| 变量 | 默认 | 作用 |
|------|------|------|
| `STREET_INGEST_MAX_SYMBOLS` | `500` | 超过则 fail loud（设 `0` 关闭上限） |
| `STREET_INGEST_RPS` | `2` | 所有行情 HTTP 的 token bucket；`0` = 不限速（仅测试） |
| `STREET_INGEST_CONCURRENCY` | `4` | 同时拉取的标的数；进度回调已加锁 |
| `STREET_INGEST_BURST` | `max(1, rps)` | 桶容量 |

Polygon 每个标的约 3 次 HTTP（K 线 + 分红 + 拆分），实际标的吞吐约为 `RPS/3`。

```bash
python -m quant.data.ingest.cli --symbols-file tickers.txt
```

规则：

- 摄取**永不原地改写**旧快照
- 增量或全量再拉发现 vendor restatement → `vendor_restatement` warning + 新快照
- 无 prior 时 `incremental` → fail loud
- Polygon 无 key → fail loud（不静默降级到 yfinance）
- 最后一根 K 线早于 14 个自然日 → 推断 `effective_to`，写入仍开放的标的池成分（不覆盖已有退出日）

```bash
python -m quant.data.ingest.cli SPY
python -m quant.data.ingest.cli SPY QQQ --mode incremental
python -m quant.data.ingest.cli --symbols-file tickers.txt
# POST /api/v1/data/ingest
#   {"symbols": ["SPY"], "provider": "polygon", "reconcile_with": "yfinance"}
# POST /api/v1/data/reconcile   # 对当前 universe 全量再拉（与 Beat 同一路径）
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
