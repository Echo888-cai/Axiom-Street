from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quant.metrics.performance import (
    compute_metrics_from_equity,
    monthly_returns_from_equity,
)


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        # LEAN chart points often use Unix ms or OLE-like values; prefer seconds if small
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError(f"Unsupported timestamp: {value!r}")


def _chart_series(result: dict[str, Any], chart: str, series: str) -> list[tuple[datetime, float]]:
    charts = result.get("charts") or result.get("Charts") or {}
    chart_obj = charts.get(chart) or {}
    series_map = chart_obj.get("series") or chart_obj.get("Series") or {}
    series_obj = series_map.get(series) or {}
    values = series_obj.get("values") or series_obj.get("Values") or []
    points: list[tuple[datetime, float]] = []
    for item in values:
        if isinstance(item, dict):
            x = item.get("x") if "x" in item else item.get("X")
            y = item.get("y") if "y" in item else item.get("Y")
            if isinstance(y, list):
                y = y[0] if y else None
            if x is None or y is None:
                continue
            points.append((_parse_ts(x), float(y)))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            points.append((_parse_ts(item[0]), float(item[1])))
    return points


def parse_lean_result(path: Path, *, risk_free_rate: float = 0.0) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    statistics = data.get("statistics") or data.get("Statistics") or {}
    runtime = data.get("runtimeStatistics") or data.get("RuntimeStatistics") or {}

    equity_points = _chart_series(data, "Strategy Equity", "Equity")
    if not equity_points:
        equity_points = _chart_series(data, "Strategy Equity", "Strategy Equity")

    benchmark_points = _chart_series(data, "Benchmark", "Benchmark")
    drawdown_points = _chart_series(data, "Drawdown", "Equity Drawdown")

    bench_map = {ts: val for ts, val in benchmark_points}
    dd_map = {ts: val for ts, val in drawdown_points}

    equity: list[dict[str, Any]] = []
    peak = None
    for ts, value in equity_points:
        peak = value if peak is None else max(peak, value)
        dd = dd_map.get(ts)
        if dd is None and peak and peak > 0:
            dd = (value / peak) - 1.0
        equity.append(
            {
                "ts": ts,
                "strategy_value": value,
                "benchmark_value": bench_map.get(ts),
                "drawdown": dd,
            }
        )

    # Normalize benchmark to start near initial capital if absolute price series
    if equity and equity[0].get("benchmark_value") is not None:
        first_strat = equity[0]["strategy_value"]
        first_bench = equity[0]["benchmark_value"]
        if first_bench and first_bench < first_strat * 0.2:
            scale = first_strat / first_bench
            for row in equity:
                if row["benchmark_value"] is not None:
                    row["benchmark_value"] = row["benchmark_value"] * scale

    orders = data.get("orders") or data.get("Orders") or {}
    trades: list[dict[str, Any]] = []
    if isinstance(orders, dict):
        order_iter = orders.values()
    else:
        order_iter = orders
    for order in order_iter:
        if not isinstance(order, dict):
            continue
        symbol = order.get("symbol") or order.get("Symbol") or {}
        if isinstance(symbol, dict):
            ticker = symbol.get("value") or symbol.get("Value") or symbol.get("symbol") or "UNKNOWN"
        else:
            ticker = str(symbol)
        direction = order.get("direction") or order.get("Direction") or "buy"
        qty = float(order.get("quantity") or order.get("Quantity") or 0)
        price = order.get("price") or order.get("Price")
        time_val = order.get("time") or order.get("Time") or order.get("createdTime")
        trades.append(
            {
                "trade_date": _parse_ts(time_val) if time_val else datetime.now(timezone.utc),
                "ticker": str(ticker).split(" ")[0],
                "direction": str(direction),
                "quantity": qty,
                "entry_price": float(price) if price is not None else None,
                "exit_price": None,
                "pnl": None,
                "return_pct": None,
                "holding_period": None,
                "commission": float(order.get("orderFeeAmount") or 0) or None,
                "slippage": None,
                "signal": None,
                "raw": order,
            }
        )

    metrics = compute_metrics_from_equity(
        equity,
        trade_count=len(trades),
        trades=trades,
        lean_statistics=statistics,
        runtime_statistics=runtime,
        risk_free_rate=risk_free_rate,
    )
    monthly = monthly_returns_from_equity(equity)

    return {
        "statistics": statistics,
        "runtime_statistics": runtime,
        "equity": equity,
        "trades": trades,
        "monthly_returns": monthly,
        "metrics": metrics,
    }


def find_result_json(results_dir: Path) -> Path | None:
    candidates = sorted(results_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        if path.name.endswith("-order-events.json"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if "statistics" in data or "Statistics" in data or "charts" in data or "Charts" in data:
            return path
    return None
