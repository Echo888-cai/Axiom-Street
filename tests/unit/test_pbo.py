"""Bailey et al. (2015) PBO / CSCV — synthetic known-behaviour cases."""

from __future__ import annotations

import numpy as np
import pytest

from quant.metrics.pbo import (
    PBOScanError,
    align_return_matrix,
    assert_configs_differ,
    choose_n_slices,
    combinatorially_symmetric_cv,
    daily_returns_from_equity,
    strategy_reads_lookback,
)
from quant.strategy_sdk.spy_200dma import DEFAULT_STRATEGY_CODE


def test_iid_noise_pbo_near_half():
    rng = np.random.default_rng(7)
    returns = rng.normal(0.0, 0.01, size=(120, 8))
    result = combinatorially_symmetric_cv(returns, n_slices=6)
    assert result.n_combinations == 20  # C(6, 3)
    assert 0.25 <= result.pbo <= 0.75


def test_overfit_config_has_high_pbo():
    rng = np.random.default_rng(3)
    t, n = 80, 12
    noise = rng.normal(0.0, 0.01, size=(t, n))
    # Config 0 is in-sample luck on the first half, then mean-reverts.
    noise[: t // 2, 0] += 0.08
    noise[t // 2 :, 0] -= 0.08
    result = combinatorially_symmetric_cv(noise, n_slices=8)
    assert result.pbo > 0.5
    assert result.passed is False


def test_true_edge_has_low_pbo():
    rng = np.random.default_rng(11)
    t, n = 80, 6
    noise = rng.normal(0.0, 0.01, size=(t, n))
    noise[:, 0] += 0.02  # genuine mean everywhere
    result = combinatorially_symmetric_cv(noise, n_slices=8)
    assert result.pbo < 0.5
    assert result.passed is True


def test_refuse_odd_slices_and_uneven_t():
    returns = np.zeros((10, 3))
    with pytest.raises(ValueError, match="even"):
        combinatorially_symmetric_cv(returns, n_slices=5)
    with pytest.raises(ValueError, match="divisible"):
        combinatorially_symmetric_cv(returns, n_slices=8)


def test_refuse_single_config():
    with pytest.raises(ValueError, match="at least 2"):
        combinatorially_symmetric_cv(np.zeros((16, 1)), n_slices=4)


def test_align_and_choose_slices():
    a = (["2020-01-02", "2020-01-03", "2020-01-06"], np.array([0.01, 0.0, -0.01]))
    b = (["2020-01-02", "2020-01-03", "2020-01-07"], np.array([0.02, 0.0, 0.01]))
    with pytest.raises(PBOScanError, match="共同交易日"):
        align_return_matrix([a, b])
    long_dates = [f"2020-01-{i:02d}" for i in range(1, 41)]
    # 40 is divisible by 4.
    series = [
        (long_dates, np.linspace(0.001, 0.002, 40)),
        (long_dates, np.linspace(-0.001, 0.003, 40)),
    ]
    dates, matrix = align_return_matrix(series)
    assert len(dates) == 40
    assert matrix.shape == (40, 2)
    assert_configs_differ(matrix)
    assert choose_n_slices(40) == 4


def test_identical_paths_fail_loud():
    dates = [f"2020-02-{i:02d}" for i in range(1, 41)]
    rets = np.full(40, 0.001)
    _, matrix = align_return_matrix([(dates, rets), (dates, rets.copy())])
    with pytest.raises(PBOScanError, match="无法区分"):
        assert_configs_differ(matrix)


def test_choose_n_slices_refuses_awkward_t():
    with pytest.raises(PBOScanError, match="不能整除"):
        choose_n_slices(41)


def test_strategy_reads_lookback():
    assert strategy_reads_lookback(
        'self.sma = self.SMA(self.spy.Symbol, int(self.GetParameter("lookback") or 200)'
    )
    assert strategy_reads_lookback(DEFAULT_STRATEGY_CODE)
    assert not strategy_reads_lookback("self.sma = self.SMA(self.spy.Symbol, 200)")


def test_daily_returns_from_equity():
    equity = [
        {"ts": "2020-01-02", "strategy_value": 100.0},
        {"ts": "2020-01-03", "strategy_value": 110.0},
        {"ts": "2020-01-06", "strategy_value": 99.0},
    ]
    dates, rets = daily_returns_from_equity(equity)
    assert dates == ["2020-01-03", "2020-01-06"]
    assert rets[0] == pytest.approx(0.1)
    assert rets[1] == pytest.approx(-0.1)
