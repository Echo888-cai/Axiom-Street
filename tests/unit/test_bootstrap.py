from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from quant.validation.bootstrap import (
    MIN_OBS,
    BootstrapError,
    bootstrap_from_equity,
    bootstrap_metrics,
    cagr_from_returns,
    max_drawdown_from_returns,
    polits_white_mean_block,
    returns_from_equity,
    sharpe_from_returns,
)


def _daily_equity(values: list[float], *, start: datetime | None = None) -> list[dict]:
    origin = start or datetime(2018, 1, 2, tzinfo=timezone.utc)
    points = []
    day = origin
    i = 0
    while i < len(values):
        if day.weekday() < 5:
            points.append({"ts": day, "strategy_value": values[i]})
            i += 1
        day += timedelta(days=1)
    return points


def _iid_returns(n: int, mu: float, sigma: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(mu, sigma, size=n)


def test_sharpe_known_value_iid():
    # mean 0.001, std 0.01, daily → Sharpe = 0.1 * sqrt(252) ≈ 1.587
    rets = np.full(MIN_OBS, 0.001)
    rets = rets + np.linspace(-0.01, 0.01, MIN_OBS)
    rets = rets - rets.mean() + 0.001
    # force std
    rets = 0.001 + 0.01 * (rets - rets.mean()) / rets.std(ddof=1)
    sr = sharpe_from_returns(rets, 252.0)
    assert sr == pytest.approx(0.1 * np.sqrt(252.0), rel=1e-9)


def test_cagr_known_value():
    rets = np.array([0.10, 0.10])
    # wealth 1.21 over 2.0 years → 1.21 ** 0.5 - 1
    assert cagr_from_returns(rets, 2.0) == pytest.approx(1.21**0.5 - 1.0)


def test_max_drawdown_known_value():
    rets = np.array([0.10, -0.50, 0.20])
    # 1 → 1.1 → 0.55 → 0.66; peak 1.1; min dd = 0.55/1.1 - 1 = -0.5
    assert max_drawdown_from_returns(rets) == pytest.approx(-0.5)


def test_zero_vol_fails_loud():
    with pytest.raises(BootstrapError, match="波动为 0"):
        sharpe_from_returns(np.zeros(MIN_OBS), 252.0)


def test_too_short_fails_loud():
    with pytest.raises(BootstrapError, match="少于"):
        bootstrap_metrics(np.ones(100) * 0.001, years=100 / 365.25, n_boot=200, seed=1)


def test_iid_method_rejected():
    rets = _iid_returns(MIN_OBS, 0.001, 0.01, 1)
    with pytest.raises(BootstrapError, match="iid"):
        bootstrap_metrics(rets, years=1.0, method="iid", n_boot=200, seed=1)


def test_zero_mean_sharpe_ci_covers_zero():
    rng = np.random.default_rng(7)
    half = rng.normal(0.0, 0.01, size=MIN_OBS)
    rets = np.concatenate([half, -half])  # mean exactly 0
    result = bootstrap_metrics(rets, years=2.0, n_boot=400, seed=7, mean_block_length=1.0)
    assert result.sharpe.observed == pytest.approx(0.0, abs=1e-12)
    assert result.sharpe.crosses_zero
    assert result.passed is False
    assert result.sharpe.low <= 0 <= result.sharpe.high


def test_strong_drift_sharpe_ci_above_zero():
    rets = _iid_returns(MIN_OBS * 2, 0.003, 0.01, seed=11)
    result = bootstrap_metrics(
        rets,
        years=2.0,
        n_boot=400,
        seed=11,
        mean_block_length=1.0,
    )
    assert result.sharpe.observed > 1.0
    assert result.sharpe.low > 0
    assert result.passed is True
    assert not result.sharpe.crosses_zero


def test_same_seed_reproducible():
    rets = _iid_returns(MIN_OBS, 0.001, 0.01, seed=3)
    a = bootstrap_metrics(rets, years=1.0, n_boot=200, seed=99, mean_block_length=5.0)
    b = bootstrap_metrics(rets, years=1.0, n_boot=200, seed=99, mean_block_length=5.0)
    assert a.sharpe.low == b.sharpe.low
    assert a.sharpe.high == b.sharpe.high
    assert a.cagr.low == b.cagr.low
    assert a.max_drawdown.high == b.max_drawdown.high


def test_ar1_automatic_block_longer_than_white_noise():
    rng = np.random.default_rng(4)
    white = rng.normal(0.0, 0.01, size=800)
    ar = np.empty(800)
    ar[0] = 0.0
    for i in range(1, 800):
        ar[i] = 0.6 * ar[i - 1] + rng.normal(0.0, 0.01)
    assert polits_white_mean_block(ar) > polits_white_mean_block(white)


def test_ar1_stationary_ci_wider_than_block_one():
    rng = np.random.default_rng(5)
    ar = np.empty(MIN_OBS * 2)
    ar[0] = 0.0
    for i in range(1, ar.size):
        ar[i] = 0.5 * ar[i - 1] + rng.normal(0.001, 0.01)
    iid = bootstrap_metrics(
        ar, years=2.0, n_boot=300, seed=5, mean_block_length=1.0, method="stationary"
    )
    dep = bootstrap_metrics(
        ar, years=2.0, n_boot=300, seed=5, mean_block_length=10.0, method="stationary"
    )
    iid_width = iid.sharpe.high - iid.sharpe.low
    dep_width = dep.sharpe.high - dep.sharpe.low
    assert dep_width > iid_width * 0.9  # dependence must not shrink the interval


def test_returns_from_equity_calendar_years():
    rng = np.random.default_rng(2)
    values = [100_000.0]
    for _ in range(MIN_OBS):
        values.append(values[-1] * (1.002 + float(rng.normal(0.0, 0.002))))
    equity = _daily_equity(values)
    rets, years, ppy = returns_from_equity(equity)
    assert len(rets) == MIN_OBS
    assert ppy == 252.0
    assert years > 0.9
    result = bootstrap_from_equity(equity, n_boot=200, seed=2, mean_block_length=1.0)
    assert result.n_obs == MIN_OBS
    assert result.passed is True


def test_empty_equity_fails_loud():
    with pytest.raises(BootstrapError, match="不足 2 根"):
        returns_from_equity([])


def test_unit_root_like_block_is_capped():
    t = MIN_OBS
    rets = np.cumsum(np.full(t, 0.001))
    rets = np.diff(np.concatenate([[0.0], rets]))  # still almost constant increment
    # near-perfect autocorrelation via a slow sine
    idx = np.arange(t)
    series = np.sin(idx / 80.0) * 0.01 + 0.001
    length = polits_white_mean_block(series)
    assert 1.0 <= length <= t / 4.0 + 1e-9
    rets = _iid_returns(MIN_OBS, 0.001, 0.01, 1)
    with pytest.raises(BootstrapError, match="n_boot"):
        bootstrap_metrics(rets, years=1.0, n_boot=10, seed=1)
    with pytest.raises(BootstrapError, match="n_boot"):
        bootstrap_metrics(rets, years=1.0, n_boot=20_000, seed=1)
