from __future__ import annotations

from datetime import datetime, timedelta, timezone

from quant.engine.errors import BacktestCancelled, EngineTimeout
from quant.metrics.performance import compute_metrics_from_equity


def _equity(n: int = 6):
    base = datetime(2020, 1, 2, tzinfo=timezone.utc)
    return [
        {
            "ts": base + timedelta(days=i),
            "strategy_value": 100_000 + i * 100,
            "benchmark_value": 100_000,
            "drawdown": 0.0,
        }
        for i in range(n)
    ]


def test_engine_timeout_is_runtime_error():
    err = EngineTimeout("LEAN exceeded 5s")
    assert isinstance(err, RuntimeError)
    assert "5s" in str(err)


def test_backtest_cancelled_is_runtime_error():
    err = BacktestCancelled("abc")
    assert isinstance(err, RuntimeError)


def test_empty_equity_does_not_invent_sharpe():
    metrics = compute_metrics_from_equity([])
    assert metrics["sharpe"] in (None, 0, 0.0) or metrics.get("final_equity") in (None, 0)
    assert metrics["extras"]["lean_statistics"] == {}


def test_single_point_equity():
    metrics = compute_metrics_from_equity(_equity(1))
    assert metrics["final_equity"] == 100_000
    assert metrics["total_return"] == 0.0


def test_all_zero_returns():
    points = _equity(8)
    for p in points:
        p["strategy_value"] = 100_000
    metrics = compute_metrics_from_equity(points)
    assert metrics["total_return"] == 0.0
    assert metrics["sharpe"] == 0.0


def test_all_positive_returns_positive_sharpe():
    metrics = compute_metrics_from_equity(_equity(10))
    assert metrics["total_return"] > 0
    assert metrics["sharpe"] > 0


def test_known_two_period_return():
    metrics = compute_metrics_from_equity(
        [
            {
                "ts": datetime(2020, 1, 2, tzinfo=timezone.utc),
                "strategy_value": 100.0,
                "benchmark_value": 100.0,
                "drawdown": 0,
            },
            {
                "ts": datetime(2020, 1, 3, tzinfo=timezone.utc),
                "strategy_value": 110.0,
                "benchmark_value": 100.0,
                "drawdown": 0,
            },
        ]
    )
    assert abs(metrics["total_return"] - 0.1) < 1e-12
