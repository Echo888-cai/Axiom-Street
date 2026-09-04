from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from quant.metrics.performance import (
    MetricFrequencyError,
    MetricParseError,
    compute_metrics_from_equity,
    monthly_returns_from_equity,
    parse_money,
    parse_pct,
    summarize_exposure,
)


def _daily_equity(values: list[float], *, start: datetime | None = None, bench_mult: float = 1.0):
    base = start or datetime(2020, 1, 2, tzinfo=timezone.utc)
    points = []
    for i, v in enumerate(values):
        points.append(
            {
                "ts": base + timedelta(days=i),
                "strategy_value": v,
                "benchmark_value": values[0] * bench_mult * (1 + 0.001 * i),
                "drawdown": None,
            }
        )
    return points


def test_parse_money_formats():
    assert parse_money("$43.00") == 43.0
    assert parse_money("$-43.00") == -43.0
    assert parse_money("($43.00)") == -43.0
    assert parse_money("1,234.56") == 1234.56
    assert parse_money("-$1,234.56") == -1234.56
    assert parse_money(-12.5) == -12.5
    assert parse_money(None) is None


def test_parse_money_rejects_garbage():
    with pytest.raises(MetricParseError):
        parse_money("n/a")
    with pytest.raises(MetricParseError):
        parse_money("")
    with pytest.raises(MetricParseError):
        parse_money("15%")


def test_parse_pct_formats():
    assert parse_pct("15%") == pytest.approx(0.15)
    assert parse_pct("0.052") == pytest.approx(0.052)
    assert parse_pct(1.23) == pytest.approx(1.23)
    assert parse_pct(None) is None
    with pytest.raises(MetricParseError):
        parse_pct("$43.00")
    with pytest.raises(MetricParseError):
        parse_pct("abc")


def test_compute_metrics_basic():
    metrics = compute_metrics_from_equity(
        _daily_equity([100_000, 101_000, 99_000, 105_000, 104_000, 110_000]), trade_count=4
    )
    assert metrics["final_equity"] == 110_000
    assert abs(metrics["total_return"] - 0.1) < 1e-9
    assert metrics["trade_count"] == 4
    assert metrics["max_drawdown"] < 0
    assert metrics["sharpe"] != 0
    assert metrics["alpha_capm"] is not None or metrics["beta"] is not None
    assert abs(metrics["calmar"] - metrics["cagr"] / abs(metrics["max_drawdown"])) < 1e-12
    assert "lean_statistics" in metrics["extras"]


def test_calmar_matches_cagr_over_drawdown():
    metrics = compute_metrics_from_equity(_daily_equity([100.0, 110.0, 90.0, 95.0]))
    assert metrics["max_drawdown"] < 0
    assert abs(metrics["calmar"] - metrics["cagr"] / abs(metrics["max_drawdown"])) < 1e-12


def test_excess_return_is_not_named_alpha():
    metrics = compute_metrics_from_equity(_daily_equity([100_000, 110_000], bench_mult=1.0))
    assert "alpha" not in metrics
    assert "excess_return" in metrics


def test_commission_from_lean_fees_string():
    metrics = compute_metrics_from_equity(
        _daily_equity([100_000, 101_000, 102_000, 103_000, 104_000]),
        lean_statistics={"Total Fees": "$43.00"},
    )
    assert metrics["commission"] == 43.0
    assert metrics["total_transaction_costs"] == 43.0
    assert metrics["extras"]["lean_statistics"]["Total Fees"] == "$43.00"


def test_unparseable_fees_raise():
    with pytest.raises(MetricParseError):
        compute_metrics_from_equity(
            _daily_equity([100_000, 101_000, 102_000, 103_000, 104_000]),
            lean_statistics={"Total Fees": "free"},
        )


def test_trade_derived_payoff_and_profit_factor():
    equity = _daily_equity([100_000, 101_000, 102_000, 103_000, 104_000, 105_000])
    trades = [
        {"pnl": 100.0, "holding_period": 2, "commission": 1.0},
        {"pnl": 50.0, "holding_period": 4, "commission": 1.0},
        {"pnl": -80.0, "holding_period": 1, "commission": 1.0},
    ]
    metrics = compute_metrics_from_equity(equity, trades=trades)
    assert metrics["trade_count"] == 3
    assert metrics["win_rate"] == pytest.approx(2 / 3)
    assert metrics["average_win"] == pytest.approx(75.0)
    assert metrics["average_loss"] == pytest.approx(-80.0)
    assert metrics["payoff_ratio"] == pytest.approx(75.0 / 80.0)
    assert metrics["profit_factor"] == pytest.approx(150.0 / 80.0)
    assert metrics["commission"] == pytest.approx(3.0)


def test_irregular_frequency_raises():
    points = []
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    for i, days in enumerate([0, 15, 30, 45]):
        points.append(
            {
                "ts": base + timedelta(days=days),
                "strategy_value": 100_000 + i * 100,
                "benchmark_value": 100_000,
                "drawdown": 0.0,
            }
        )
    with pytest.raises(MetricFrequencyError):
        compute_metrics_from_equity(points)


def test_monthly_returns():
    points = []
    value = 100_000.0
    for i in range(6):
        value *= 1.01
        points.append(
            {
                "ts": datetime(2022, 1 + i, 28, tzinfo=timezone.utc),
                "strategy_value": value,
                "benchmark_value": value,
                "drawdown": 0.0,
            }
        )
    monthly = monthly_returns_from_equity(points)
    assert len(monthly) >= 4
    assert all("year" in m and "month" in m and "return_pct" in m for m in monthly)


def test_does_not_prefer_lean_sharpe():
    metrics = compute_metrics_from_equity(
        _daily_equity([100_000, 101_000, 99_000, 102_000, 103_000, 104_000]),
        lean_statistics={"Sharpe Ratio": "99.0", "Net Profit": "50%", "Drawdown": "90%"},
    )
    assert metrics["sharpe"] != 99.0
    assert abs(metrics["total_return"] - 0.04) < 1e-9
    assert metrics["max_drawdown"] > -0.9


def test_tail_risk_metrics_present():
    values = [100_000]
    v = 100_000.0
    for i in range(30):
        v *= 1.002 if i % 3 else 0.997
        values.append(v)
    metrics = compute_metrics_from_equity(_daily_equity(values))
    assert metrics["var_95"] is not None
    assert metrics["cvar_95"] is not None
    assert metrics["skewness"] is not None
    assert metrics["kurtosis"] is not None


def test_parse_money_unicode_minus():
    assert parse_money("−12.5") == -12.5


def test_parse_money_usd_suffix():
    assert parse_money("$10 USD") == 10.0


def test_weekly_frequency_accepted():
    points = []
    base = datetime(2020, 1, 6, tzinfo=timezone.utc)
    value = 100_000.0
    for i in range(8):
        value *= 1.01
        points.append(
            {
                "ts": base + timedelta(days=7 * i),
                "strategy_value": value,
                "benchmark_value": 100_000.0,
                "drawdown": 0.0,
            }
        )
    metrics = compute_metrics_from_equity(points)
    assert metrics["sharpe"] is not None


def test_empty_equity_returns_zero_sharpe():
    metrics = compute_metrics_from_equity([])
    assert metrics["sharpe"] == 0.0
    assert metrics["final_equity"] is None or metrics["final_equity"] == 0.0


def test_exposure_from_time_series():
    metrics = compute_metrics_from_equity(
        _daily_equity([100.0, 101.0, 102.0]),
        time_series=[
            {"name": "exposure_long", "value": 1.0},
            {"name": "exposure_long", "value": 0.0},
            {"name": "exposure_short", "value": 0.0},
            {"name": "exposure_short", "value": 0.0},
            {"name": "turnover", "value": 0.2},
        ],
    )
    assert metrics["gross_exposure"] == pytest.approx(0.5)
    assert metrics["net_exposure"] == pytest.approx(0.5)
    assert metrics["turnover"] == pytest.approx(0.2)
    assert summarize_exposure([])["turnover"] is None
