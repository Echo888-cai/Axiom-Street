from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from quant.validation.regime import (
    BEAR_DRAWDOWN,
    RegimeError,
    label_bull_bear,
    label_rate,
    label_vol,
    rate_regime,
    score_regime,
    series_from_equity,
    sharpe_from_slice,
    win_rate_from_slice,
)


def _ts(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def _weekdays(start: date, end: date) -> list[date]:
    days: list[date] = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def _equity_from_levels(
    days: list[date], strategy: list[float], benchmark: list[float]
) -> list[dict]:
    return [
        {"ts": _ts(day), "strategy_value": strat, "benchmark_value": bench}
        for day, strat, bench in zip(days, strategy, benchmark)
    ]


def test_bear_starts_at_exactly_20_pct_drawdown():
    levels = np.array([100.0, 110.0, 120.0, 96.0])
    labels = label_bull_bear(levels)
    assert list(labels) == ["bull", "bull", "bear"]
    assert 96.0 / 120.0 - 1.0 == pytest.approx(BEAR_DRAWDOWN)


def test_bear_ends_only_at_new_high():
    levels = np.array([100.0, 120.0, 90.0, 88.0, 119.0, 121.0])
    labels = label_bull_bear(levels)
    assert list(labels) == ["bull", "bear", "bear", "bear", "bull"]


def test_positive_threshold_fails_loud():
    with pytest.raises(RegimeError, match="必须 < 0"):
        label_bull_bear(np.array([100.0, 110.0]), threshold=0.2)


def test_vol_split_above_median_is_high():
    calm = np.full(40, 0.001)
    wild = np.array([0.05, -0.05] * 20)
    rets = np.concatenate([calm, wild])
    labels = label_vol(rets, window=10)
    classified = [item for item in labels if item]
    assert "high_vol" in classified
    assert "low_vol" in classified
    # last of the calm window is low; last of the wild window is high
    assert labels[9] == "low_vol"
    assert labels[-1] == "high_vol"


def test_constant_vol_cannot_cover_both_sides():
    rets = np.full(80, 0.01)
    labels = label_vol(rets, window=21)
    assert set(labels[20:]) == {"low_vol"}


def test_rate_calendar_known_dates():
    assert rate_regime(date(2018, 6, 1)) == "hike"
    assert rate_regime(date(2019, 8, 1)) == "cut"
    assert rate_regime(date(2014, 6, 1)) == "hold"
    assert rate_regime(date(2022, 3, 16)) == "hike"
    assert rate_regime(date(2024, 9, 18)) == "cut"
    days = [date(2018, 6, 1), date(2019, 8, 1), date(2014, 6, 1)]
    assert list(label_rate(days)) == ["hike", "cut", "hold"]


def test_cash_slice_sharpe_is_zero_not_undefined():
    assert sharpe_from_slice(np.zeros(60), 252.0) == 0.0
    assert win_rate_from_slice(np.zeros(60)) == 0.0


def test_constant_nonzero_return_fails_loud():
    with pytest.raises(RegimeError, match="没有定义"):
        sharpe_from_slice(np.full(60, 0.01), 252.0)


def test_win_rate_known_value():
    rets = np.array([0.01, -0.01, 0.02, 0.0])
    assert win_rate_from_slice(rets) == pytest.approx(0.5)


def test_missing_benchmark_fails_loud():
    equity = [
        {"ts": _ts(date(2018, 1, 2)), "strategy_value": 100.0},
        {"ts": _ts(date(2018, 1, 3)), "strategy_value": 101.0},
    ]
    with pytest.raises(RegimeError, match="基准净值"):
        series_from_equity(equity)


def _two_year_market(*, strategy: str) -> list[dict]:
    """2018–2019 path: calm hike, 20%+ crash (bear + high vol), cut-year recovery.

    ``strategy='robust'``: small positive jitter in every regime.
    ``strategy='hold'``: tracks the benchmark (loses in the crash).
    ``strategy='cash_in_bear'``: tracks in bull, flat in bear.
    """
    days = _weekdays(date(2018, 1, 2), date(2019, 12, 31))
    crash_start = next(day for day in days if day >= date(2018, 7, 1))
    bench = 100.0
    strat = 100.0
    in_bear = False
    peak = bench
    strategy_levels = [strat]
    benchmark_levels = [bench]
    for i, day in enumerate(days[1:]):
        if day == crash_start:
            bench_ret = -0.21
        elif date(2018, 7, 1) <= day <= date(2018, 12, 31):
            bench_ret = -0.008 + 0.006 * ((i % 5) - 2) / 2.0
        elif day.year == 2019 and day.month <= 6:
            bench_ret = 0.006 + 0.001 * ((i % 5) - 2) / 2.0
        else:
            bench_ret = 0.0015 + 0.0008 * ((i % 5) - 2) / 2.0
        bench *= 1.0 + bench_ret
        if bench > peak:
            peak = bench
            in_bear = False
        if bench / peak - 1.0 <= BEAR_DRAWDOWN:
            in_bear = True
        if strategy == "hold":
            strat *= 1.0 + bench_ret
        elif strategy == "cash_in_bear":
            strat *= 1.0 if in_bear else (1.0 + bench_ret)
        else:
            strat *= 1.0 + 0.001 + 0.0006 * ((i % 7) - 3) / 3.0
        strategy_levels.append(strat)
        benchmark_levels.append(bench)
    return _equity_from_levels(days, strategy_levels, benchmark_levels)


def test_robust_strategy_passes_all_axes():
    result = score_regime(_two_year_market(strategy="robust"))
    by_key = {item.key: item for item in result.slices}
    assert by_key["bull"].covered and by_key["bear"].covered
    assert by_key["high_vol"].covered and by_key["low_vol"].covered
    assert by_key["hike"].covered and by_key["cut"].covered
    assert by_key["bull"].sharpe is not None and by_key["bull"].sharpe > 0
    assert by_key["bear"].sharpe is not None and by_key["bear"].sharpe > 0
    assert result.passed is True
    assert result.single_regime is False


def test_buy_and_hold_fails_in_bear():
    result = score_regime(_two_year_market(strategy="hold"))
    by_key = {item.key: item for item in result.slices}
    assert by_key["bear"].covered
    assert by_key["bear"].sharpe is not None
    assert by_key["bear"].sharpe < 0
    assert result.passed is False
    assert "熊市" in result.reason


def test_cash_in_bear_is_annotated_not_failed():
    result = score_regime(_two_year_market(strategy="cash_in_bear"))
    by_key = {item.key: item for item in result.slices}
    assert by_key["bear"].sharpe == pytest.approx(0.0)
    assert by_key["bull"].sharpe is not None and by_key["bull"].sharpe > 0
    assert result.passed is True
    assert result.single_regime is True
    assert result.concentrated_in == "bull"


def test_sample_without_rate_cycle_fails_loud():
    days = _weekdays(date(2014, 1, 2), date(2014, 12, 31))
    levels = [100.0]
    for i in range(1, len(days)):
        shock = -0.25 if 80 <= i <= 160 else 0.003
        levels.append(levels[-1] * (1.0 + shock + 0.004 * ((i % 5) - 2) / 2.0))
    strat = [100.0]
    for i in range(1, len(days)):
        strat.append(strat[-1] * (1.001 + 0.0005 * ((i % 7) - 3) / 3.0))
    result = score_regime(_equity_from_levels(days, strat, levels))
    assert result.passed is False
    assert "加息" in result.reason or "降息" in result.reason


def test_stress_window_reported_when_in_sample():
    days = _weekdays(date(2020, 2, 3), date(2020, 4, 30))
    # Too short for axis gates; still reports the COVID window.
    bench = [100.0]
    strat = [100.0]
    for i in range(1, len(days)):
        bench.append(bench[-1] * (0.97 if days[i].month == 3 else 1.002))
        strat.append(strat[-1] * (1.001 + 0.0004 * ((i % 5) - 2) / 2.0))
    result = score_regime(_equity_from_levels(days, strat, bench))
    covid = next(item for item in result.slices if item.key == "covid_2020_03")
    assert covid.n_obs >= 10
    assert covid.covered is True
    assert result.passed is False  # 2020-02..04 is all cut, no hike, no 60-day bull/bear


def test_empty_equity_fails_loud():
    with pytest.raises(RegimeError, match="不足 2 根"):
        score_regime([])
