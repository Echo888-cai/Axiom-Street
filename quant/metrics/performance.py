from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


class MetricParseError(ValueError):
    """Raised when a statistic string cannot be parsed. Fail loud — never default."""


class MetricFrequencyError(ValueError):
    """Raised when the equity curve is not a supported sampling frequency."""


_TRADING_DAYS_PER_YEAR = 252.0
_CALENDAR_DAYS_PER_YEAR = 365.25


def parse_pct(value: Any) -> float | None:
    """Parse a percentage or unit-interval number. ``None`` stays ``None``.

    Accepts ``15%``, ``15``, ``0.15``. Bare numbers >= 1 are treated as percent
    points (LEAN's ``Win Rate: 43`` vs ``43%``). Callers that already have a
    unit interval should pass a float.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not np.isfinite(value):
            raise MetricParseError(f"Non-finite percentage: {value!r}")
        return float(value)
    text = str(value).strip().replace(",", "")
    if text == "":
        raise MetricParseError("Empty percentage string")
    if text.endswith("%"):
        try:
            return float(text[:-1]) / 100.0
        except ValueError as exc:
            raise MetricParseError(f"Unparseable percentage: {value!r}") from exc
    try:
        return float(text)
    except ValueError as exc:
        raise MetricParseError(f"Unparseable percentage: {value!r}") from exc


def parse_money(value: Any) -> float | None:
    """Parse a currency amount. ``None`` stays ``None``; anything else must parse.

    Accepts ``$43.00``, ``$-43.00``, ``($43.00)``, ``1,234.56``, ``-$1,234.56``.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not np.isfinite(value):
            raise MetricParseError(f"Non-finite money: {value!r}")
        return float(value)
    text = str(value).strip()
    if text == "":
        raise MetricParseError("Empty money string")
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    text = text.replace(",", "").replace("$", "").replace("USD", "").strip()
    if text.startswith("−"):  # unicode minus
        text = "-" + text[1:]
    try:
        amount = float(text)
    except ValueError as exc:
        raise MetricParseError(f"Unparseable money: {value!r}") from exc
    if negative:
        amount = -abs(amount)
    return amount


def _optional_money(stats: Mapping[str, Any], key: str) -> float | None:
    if key not in stats:
        return None
    return parse_money(stats[key])


def _to_frame(equity: list[dict[str, Any]]) -> pd.DataFrame:
    if not equity:
        return pd.DataFrame(columns=["ts", "strategy_value", "benchmark_value", "drawdown"])
    df = pd.DataFrame(equity)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.sort_values("ts").drop_duplicates("ts")
    return df


def _periods_per_year(ts: pd.Series) -> float:
    if len(ts) < 2:
        return _TRADING_DAYS_PER_YEAR
    deltas = ts.diff().dropna().dt.total_seconds() / 86400.0
    median = float(deltas.median())
    if 0.4 <= median <= 2.0:
        return _TRADING_DAYS_PER_YEAR
    if 4.0 <= median <= 10.0:
        return 52.0
    if 20.0 <= median <= 45.0:
        return 12.0
    raise MetricFrequencyError(
        f"Equity curve sampling is not daily/weekly/monthly (median spacing {median:.2f} days)"
    )


def _empty_metrics(
    *,
    trade_count: int,
    extras: dict[str, Any],
) -> dict[str, Any]:
    return {
        "total_return": 0.0,
        "cagr": 0.0,
        "annualized_return": 0.0,
        "benchmark_return": None,
        "excess_return": None,
        "alpha_capm": None,
        "beta": None,
        "information_ratio": None,
        "tracking_error": None,
        "volatility": 0.0,
        "max_drawdown": 0.0,
        "average_drawdown": 0.0,
        "drawdown_duration_days": 0.0,
        "downside_deviation": 0.0,
        "sharpe": 0.0,
        "sortino": 0.0,
        "calmar": 0.0,
        "win_rate": None,
        "profit_factor": None,
        "average_win": None,
        "average_loss": None,
        "payoff_ratio": None,
        "trade_count": trade_count,
        "turnover": None,
        "holding_period": None,
        "gross_exposure": None,
        "net_exposure": None,
        "leverage": None,
        "cash": None,
        "commission": None,
        "slippage": None,
        "total_transaction_costs": None,
        "final_equity": None,
        "tail_ratio": None,
        "skewness": None,
        "kurtosis": None,
        "var_95": None,
        "cvar_95": None,
        "omega_ratio": None,
        "extras": extras,
    }


def _trade_stats(trades: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    if not trades:
        return {
            "win_rate": None,
            "profit_factor": None,
            "average_win": None,
            "average_loss": None,
            "payoff_ratio": None,
            "holding_period": None,
            "commission": None,
        }
    pnls: list[float] = []
    holds: list[float] = []
    commissions: list[float] = []
    for trade in trades:
        pnl = trade.get("pnl")
        if pnl is not None:
            pnls.append(float(pnl))
        hp = trade.get("holding_period")
        if hp is not None:
            holds.append(float(hp))
        fee = trade.get("commission")
        if fee is not None:
            commissions.append(float(fee))
    out: dict[str, Any] = {
        "win_rate": None,
        "profit_factor": None,
        "average_win": None,
        "average_loss": None,
        "payoff_ratio": None,
        "holding_period": float(np.mean(holds)) if holds else None,
        "commission": float(np.sum(commissions)) if commissions else None,
    }
    if not pnls:
        return out
    arr = np.asarray(pnls, dtype=float)
    wins = arr[arr > 0]
    losses = arr[arr < 0]
    out["win_rate"] = float(np.mean(arr > 0)) if len(arr) else None
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(np.abs(losses.sum())) if len(losses) else 0.0
    out["profit_factor"] = (gross_profit / gross_loss) if gross_loss > 0 else None
    out["average_win"] = float(wins.mean()) if len(wins) else None
    out["average_loss"] = float(losses.mean()) if len(losses) else None
    if out["average_win"] is not None and out["average_loss"] not in (None, 0.0):
        out["payoff_ratio"] = abs(out["average_win"] / out["average_loss"])
    return out


def summarize_exposure(
    time_series: Sequence[Mapping[str, Any]] | None,
) -> dict[str, float | None]:
    """Mean net/gross exposure and turnover from parsed LEAN charts.

    Missing series stay ``None`` — never invent a quiet zero. Long without
    short is treated as long-only (short = 0) because LEAN sometimes omits
    the empty short series.
    """
    empty: dict[str, float | None] = {
        "turnover": None,
        "gross_exposure": None,
        "net_exposure": None,
    }
    if not time_series:
        return empty
    by_name: dict[str, list[float]] = {}
    for row in time_series:
        name = str(row.get("name") or "")
        if not name:
            continue
        try:
            value = float(row["value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise MetricParseError(f"暴露序列无法解析: {row!r}") from exc
        by_name.setdefault(name, []).append(value)

    long_s = by_name.get("exposure_long") or []
    short_s = by_name.get("exposure_short") or []
    turn_s = by_name.get("turnover") or []
    if long_s and short_s and len(long_s) != len(short_s):
        raise MetricParseError(f"long/short 暴露长度不一致: {len(long_s)} vs {len(short_s)}")
    net: float | None = None
    gross: float | None = None
    if long_s and short_s:
        nets = [lo - sh for lo, sh in zip(long_s, short_s)]
        grosses = [lo + sh for lo, sh in zip(long_s, short_s)]
        net = float(sum(nets) / len(nets))
        gross = float(sum(grosses) / len(grosses))
    elif long_s:
        net = float(sum(long_s) / len(long_s))
        gross = net
    elif short_s:
        mean_short = float(sum(short_s) / len(short_s))
        net = -mean_short
        gross = mean_short
    turnover = float(sum(turn_s) / len(turn_s)) if turn_s else None
    return {"turnover": turnover, "gross_exposure": gross, "net_exposure": net}


def _ols_alpha_beta(y: np.ndarray, x: np.ndarray) -> tuple[float | None, float | None]:
    if len(y) < 3 or len(x) < 3:
        return None, None
    var_x = float(np.var(x, ddof=1))
    if var_x == 0.0:
        return None, None
    cov = float(np.cov(x, y, ddof=1)[0, 1])
    beta = cov / var_x
    alpha = float(y.mean() - beta * x.mean())
    return alpha, float(beta)


def compute_metrics_from_equity(
    equity: list[dict[str, Any]],
    *,
    trade_count: int | None = None,
    trades: Sequence[Mapping[str, Any]] | None = None,
    time_series: Sequence[Mapping[str, Any]] | None = None,
    lean_statistics: dict[str, Any] | None = None,
    runtime_statistics: dict[str, Any] | None = None,
    risk_free_rate: float = 0.0,
    risk_free_daily: pd.Series | None = None,
) -> dict[str, Any]:
    """Compute Axiom metrics from the equity curve.

    LEAN statistics are stored in ``extras`` for cross-check only — they never
    overwrite Axiom-computed fields.

    Default ``risk_free_rate`` is 0. LEAN's own Sharpe uses a 1% default; pass
    ``risk_free_rate=0.01`` when reconciling against LEAN statistics.
    """
    df = _to_frame(equity)
    lean_statistics = dict(lean_statistics or {})
    runtime_statistics = dict(runtime_statistics or {})
    extras = {
        "lean_statistics": lean_statistics,
        "runtime_statistics": runtime_statistics,
        "risk_free_rate": risk_free_rate,
    }
    trade_stats = _trade_stats(trades)
    resolved_trade_count = (
        trade_count if trade_count is not None else (len(trades) if trades else 0)
    )

    if df.empty:
        empty = _empty_metrics(trade_count=resolved_trade_count, extras=extras)
        empty["commission"] = trade_stats["commission"]
        if empty["commission"] is None:
            empty["commission"] = _optional_money(lean_statistics, "Total Fees")
        empty["total_transaction_costs"] = empty["commission"]
        return empty

    values = df["strategy_value"].astype(float)
    rets = values.pct_change().dropna()
    start_value = float(values.iloc[0])
    end_value = float(values.iloc[-1])
    total_return = (end_value / start_value) - 1.0 if start_value else 0.0

    ppy = _periods_per_year(df["ts"])
    days = max((df["ts"].iloc[-1] - df["ts"].iloc[0]).total_seconds() / 86400.0, 1.0)
    years = days / _CALENDAR_DAYS_PER_YEAR
    cagr = (end_value / start_value) ** (1 / years) - 1.0 if start_value > 0 and years > 0 else 0.0

    rf_period = np.full(len(rets), risk_free_rate / ppy, dtype=float)
    if risk_free_daily is not None and len(rets):
        aligned_rf = risk_free_daily.reindex(rets.index).astype(float)
        if aligned_rf.notna().any():
            rf_period = aligned_rf.fillna(risk_free_rate / ppy).to_numpy()

    excess = rets.to_numpy(dtype=float) - rf_period
    vol = float(rets.std(ddof=1) * np.sqrt(ppy)) if len(rets) > 1 else 0.0
    rets_std = float(rets.std(ddof=1)) if len(rets) > 1 else 0.0
    sharpe = float(np.mean(excess) / rets_std * np.sqrt(ppy)) if rets_std else 0.0

    downside = rets[rets < 0]
    downside_dev = float(downside.std(ddof=1) * np.sqrt(ppy)) if len(downside) > 1 else 0.0
    down_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    sortino = float(np.mean(excess) / down_std * np.sqrt(ppy)) if down_std else 0.0

    rolling_peak = values.cummax()
    drawdown = values / rolling_peak - 1.0
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0
    avg_dd = float(drawdown[drawdown < 0].mean()) if (drawdown < 0).any() else 0.0

    underwater = drawdown < 0
    duration = 0
    max_duration = 0
    prev_ts: datetime | None = None
    for ts, flag in zip(df["ts"], underwater):
        if flag:
            if prev_ts is not None:
                duration += max(int((ts - prev_ts).days), 1)
            else:
                duration = 1
            max_duration = max(max_duration, duration)
        else:
            duration = 0
        prev_ts = ts

    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0

    benchmark_return = None
    excess_return = None
    beta = None
    alpha_capm = None
    information_ratio = None
    tracking_error = None
    if "benchmark_value" in df.columns and df["benchmark_value"].notna().any():
        b = df["benchmark_value"].astype(float)
        b_valid = b.dropna()
        if len(b_valid) >= 2 and float(b_valid.iloc[0]) != 0:
            benchmark_return = float(b_valid.iloc[-1] / b_valid.iloc[0] - 1.0)
            excess_return = total_return - benchmark_return
        bench_rets = b.pct_change()
        aligned = pd.DataFrame({"r": rets, "b": bench_rets}).dropna()
        if len(aligned) >= 3:
            y = aligned["r"].to_numpy(dtype=float) - (risk_free_rate / ppy)
            x = aligned["b"].to_numpy(dtype=float) - (risk_free_rate / ppy)
            a_period, beta = _ols_alpha_beta(y, x)
            if a_period is not None:
                alpha_capm = float(a_period * ppy)
            active = aligned["r"] - aligned["b"]
            active_std = float(active.std(ddof=1))
            if active_std:
                tracking_error = float(active_std * np.sqrt(ppy))
                information_ratio = float(active.mean() / active_std * np.sqrt(ppy))

    tail_ratio = None
    skewness = None
    kurtosis = None
    var_95 = None
    cvar_95 = None
    omega_ratio = None
    if len(rets) >= 5:
        q05 = float(rets.quantile(0.05))
        q95 = float(rets.quantile(0.95))
        if q05 != 0:
            tail_ratio = abs(q95 / q05)
        skewness = float(rets.skew())
        kurtosis = float(rets.kurtosis())
        var_95 = float(-q05)
        tail = rets[rets <= q05]
        cvar_95 = float(-tail.mean()) if len(tail) else var_95
        gains = float(rets[rets > 0].sum())
        losses = float(np.abs(rets[rets < 0].sum()))
        omega_ratio = (gains / losses) if losses > 0 else None

    commission = trade_stats["commission"]
    if commission is None:
        commission = _optional_money(lean_statistics, "Total Fees")
    exposure = summarize_exposure(time_series)

    return {
        "total_return": total_return,
        "cagr": cagr,
        "annualized_return": cagr,
        "benchmark_return": benchmark_return,
        "excess_return": excess_return,
        "alpha_capm": alpha_capm,
        "beta": beta,
        "information_ratio": information_ratio,
        "tracking_error": tracking_error,
        "volatility": vol,
        "max_drawdown": max_dd,
        "average_drawdown": avg_dd,
        "drawdown_duration_days": float(max_duration),
        "downside_deviation": downside_dev,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "win_rate": trade_stats["win_rate"],
        "profit_factor": trade_stats["profit_factor"],
        "average_win": trade_stats["average_win"],
        "average_loss": trade_stats["average_loss"],
        "payoff_ratio": trade_stats["payoff_ratio"],
        "trade_count": resolved_trade_count,
        "turnover": exposure["turnover"],
        "holding_period": trade_stats["holding_period"],
        "gross_exposure": exposure["gross_exposure"],
        "net_exposure": exposure["net_exposure"],
        "leverage": None,
        "cash": None,
        "commission": commission,
        "slippage": None,
        "total_transaction_costs": commission,
        "final_equity": end_value,
        "tail_ratio": tail_ratio,
        "skewness": skewness,
        "kurtosis": kurtosis,
        "var_95": var_95,
        "cvar_95": cvar_95,
        "omega_ratio": omega_ratio,
        "extras": extras,
    }


def monthly_returns_from_equity(equity: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = _to_frame(equity)
    if df.empty:
        return []
    s = df.set_index("ts")["strategy_value"].astype(float)
    monthly = s.resample("ME").last().dropna()
    rets = monthly.pct_change().dropna()
    out: list[dict[str, Any]] = []
    for ts, value in rets.items():
        out.append({"year": int(ts.year), "month": int(ts.month), "return_pct": float(value)})
    return out
