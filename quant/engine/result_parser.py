from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quant.metrics.performance import (
    compute_metrics_from_equity,
    monthly_returns_from_equity,
)

_MONITOR_JSON = re.compile(
    r"(data-monitor-report|failed-data-requests|succeeded-data-requests|-order-events)",
    re.IGNORECASE,
)

_DIRECTION = {0: "LONG", 1: "SHORT", "0": "LONG", "1": "SHORT"}


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError(f"Unsupported timestamp: {value!r}")


def parse_duration_days(value: Any) -> float | None:
    """Parse a .NET TimeSpan (``81.23:00:00``) or hour count into days."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    if "." in text and ":" in text:
        days_part, rest = text.split(".", 1)
        try:
            days = float(days_part)
            hours, minutes, seconds = rest.split(":")
            return days + int(hours) / 24.0 + int(minutes) / 1440.0 + float(seconds) / 86400.0
        except ValueError:
            return None
    if ":" in text:
        parts = text.split(":")
        try:
            hour_count = int(parts[0])
            minute_count = int(parts[1]) if len(parts) > 1 else 0
            second_count = float(parts[2]) if len(parts) > 2 else 0.0
            return hour_count / 24.0 + minute_count / 1440.0 + second_count / 86400.0
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


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


def _time_series(points: list[tuple[datetime, float]], name: str) -> list[dict[str, Any]]:
    return [{"name": name, "ts": ts, "value": value} for ts, value in points]


def _ticker(symbol: Any) -> str:
    if isinstance(symbol, dict):
        return str(symbol.get("Value") or symbol.get("value") or symbol.get("symbol") or "UNKNOWN")
    return str(symbol).split(" ")[0]


def _closed_trades(data: dict[str, Any]) -> list[dict[str, Any]]:
    total = data.get("TotalPerformance") or data.get("totalPerformance") or {}
    raw = total.get("ClosedTrades") or total.get("closedTrades") or []
    trades: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        entry = item.get("EntryPrice") if "EntryPrice" in item else item.get("entryPrice")
        exit_px = item.get("ExitPrice") if "ExitPrice" in item else item.get("exitPrice")
        pnl = item.get("ProfitLoss") if "ProfitLoss" in item else item.get("profitLoss")
        qty_raw = item.get("Quantity") if "Quantity" in item else item.get("quantity")
        qty = float(qty_raw or 0)
        direction = item.get("Direction") if "Direction" in item else item.get("direction")
        direction_label = _DIRECTION.get(direction, str(direction).upper() if direction else "LONG")
        entry_time = item.get("EntryTime") or item.get("entryTime")
        hold = parse_duration_days(item.get("Duration") or item.get("duration"))
        ret = None
        if entry is not None and pnl is not None and qty:
            entry_px = float(entry)
            if entry_px:
                ret = float(pnl) / abs(entry_px * qty)
        trades.append(
            {
                "trade_date": _parse_ts(entry_time) if entry_time else datetime.now(timezone.utc),
                "ticker": _ticker(item.get("Symbol") or item.get("symbol")),
                "direction": direction_label,
                "quantity": qty,
                "entry_price": float(entry) if entry is not None else None,
                "exit_price": float(exit_px) if exit_px is not None else None,
                "pnl": float(pnl) if pnl is not None else None,
                "return_pct": ret,
                "holding_period": hold,
                "commission": float(item["TotalFees"])
                if item.get("TotalFees") is not None
                else (float(item["totalFees"]) if item.get("totalFees") is not None else None),
                "slippage": None,
                "signal": None,
                "raw": item,
            }
        )
    return trades


def _orders_as_trades(data: dict[str, Any]) -> list[dict[str, Any]]:
    orders = data.get("orders") or data.get("Orders") or {}
    order_iter = orders.values() if isinstance(orders, dict) else orders
    trades: list[dict[str, Any]] = []
    for order in order_iter:
        if not isinstance(order, dict):
            continue
        qty = float(order.get("quantity") or order.get("Quantity") or 0)
        price = order.get("price") or order.get("Price")
        time_val = order.get("time") or order.get("Time") or order.get("createdTime")
        direction = order.get("direction") or order.get("Direction") or "buy"
        trades.append(
            {
                "trade_date": _parse_ts(time_val) if time_val else datetime.now(timezone.utc),
                "ticker": _ticker(order.get("symbol") or order.get("Symbol")),
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
    return trades


def _rolling_windows(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("RollingWindow") or data.get("rollingWindow") or {}
    if not isinstance(raw, dict):
        return []
    out: list[dict[str, Any]] = []
    for key, window in raw.items():
        if not isinstance(window, dict):
            continue
        ps = window.get("PortfolioStatistics") or window.get("portfolioStatistics") or {}
        period_end = None
        if "_" in str(key):
            stamp = str(key).split("_", 1)[-1]
            if len(stamp) == 8 and stamp.isdigit():
                period_end = datetime(
                    int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]), tzinfo=timezone.utc
                )

        def _f(name: str) -> float | None:
            if name not in ps:
                return None
            try:
                return float(ps[name])
            except (TypeError, ValueError):
                return None

        out.append(
            {
                "window_key": str(key),
                "period_end": period_end,
                "sharpe": _f("SharpeRatio"),
                "var_95": _f("ValueAtRisk95"),
                "var_99": _f("ValueAtRisk99"),
                "probabilistic_sharpe": _f("ProbabilisticSharpeRatio"),
                "end_equity": _f("EndEquity"),
                "drawdown": _f("Drawdown"),
                "extras": ps,
            }
        )
    return out


def rebase_benchmark(
    equity: list[dict[str, Any]],
    *,
    enabled: bool = True,
    threshold: float = 0.2,
) -> dict[str, Any]:
    """Scale a raw price benchmark onto the strategy starting equity when asked.

    The decision is recorded so callers can see whether numbers were adjusted.
    """
    info = {
        "benchmark_rebased": False,
        "benchmark_rebase_scale": 1.0,
        "benchmark_rebase_enabled": enabled,
    }
    if not enabled or not equity:
        return info
    first_strat = equity[0].get("strategy_value")
    first_bench = equity[0].get("benchmark_value")
    if not first_strat or not first_bench:
        return info
    if first_bench < first_strat * threshold:
        scale = float(first_strat) / float(first_bench)
        for row in equity:
            if row.get("benchmark_value") is not None:
                row["benchmark_value"] = row["benchmark_value"] * scale
        info["benchmark_rebased"] = True
        info["benchmark_rebase_scale"] = scale
    return info


def parse_lean_result(
    path: Path,
    *,
    risk_free_rate: float = 0.0,
    rebase_benchmark_enabled: bool = True,
) -> dict[str, Any]:
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

    rebase_info = rebase_benchmark(equity, enabled=rebase_benchmark_enabled)

    closed = _closed_trades(data)
    trades = closed if closed else _orders_as_trades(data)

    time_series: list[dict[str, Any]] = []
    time_series.extend(
        _time_series(_chart_series(data, "Exposure", "Equity - Long Ratio"), "exposure_long")
    )
    time_series.extend(
        _time_series(_chart_series(data, "Exposure", "Equity - Short Ratio"), "exposure_short")
    )
    time_series.extend(
        _time_series(_chart_series(data, "Portfolio Turnover", "Portfolio Turnover"), "turnover")
    )

    rolling = _rolling_windows(data)

    metrics = compute_metrics_from_equity(
        equity,
        trade_count=len(trades),
        trades=trades,
        time_series=time_series,
        lean_statistics=statistics,
        runtime_statistics=runtime,
        risk_free_rate=risk_free_rate,
    )
    metrics["extras"] = {
        **metrics.get("extras", {}),
        **rebase_info,
        "lean_beta": statistics.get("Beta"),
        "lean_information_ratio": statistics.get("Information Ratio"),
        "lean_treynor": statistics.get("Treynor Ratio"),
        "lean_tracking_error": statistics.get("Tracking Error"),
        "closed_trade_count": len(closed),
        "order_count": len(_orders_as_trades(data)) if not closed else None,
    }
    monthly = monthly_returns_from_equity(equity)

    return {
        "statistics": statistics,
        "runtime_statistics": runtime,
        "equity": equity,
        "trades": trades,
        "monthly_returns": monthly,
        "metrics": metrics,
        "rolling_windows": rolling,
        "time_series": time_series,
    }


def find_result_json(results_dir: Path, algorithm_class: str | None = None) -> Path | None:
    if algorithm_class:
        exact = results_dir / f"{algorithm_class}.json"
        if exact.exists():
            return exact
    candidates = sorted(results_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        if _MONITOR_JSON.search(path.name):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if ("statistics" in data or "Statistics" in data) and (
            "charts" in data or "Charts" in data
        ):
            return path
    return None
