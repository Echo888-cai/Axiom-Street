from __future__ import annotations

import numpy as np
import pytest

from quant.validation.spa import (
    DEFAULT_ALPHA,
    MIN_MODELS,
    MIN_OBS,
    SpaError,
    bartlett_long_run_variance,
    spa_test,
)


def _zero_mean(n: int, sigma: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    half = rng.normal(0.0, sigma, size=n)
    # Exact mean 0 after concatenating with the negation is n*2; trim to n.
    raw = np.concatenate([half, -half])[:n]
    return raw - raw.mean()


def test_k_one_fails_loud():
    with pytest.raises(SpaError, match="至少需要"):
        spa_test(np.zeros((MIN_OBS, 1)), n_boot=200, seed=1)


def test_short_panel_fails_loud():
    panel = np.column_stack([_zero_mean(100, 0.01, 1), _zero_mean(100, 0.01, 2)])
    with pytest.raises(SpaError, match="少于"):
        spa_test(panel, n_boot=200, seed=1)


def test_identical_columns_fail_loud():
    col = 0.001 + _zero_mean(MIN_OBS, 0.01, 3) * 0.1
    with pytest.raises(SpaError, match="无法区分"):
        spa_test(np.column_stack([col, col]), n_boot=200, seed=1)


def test_iid_method_is_not_an_option():
    # spa_test has no method=iid; resampling goes through stationary indices only.
    panel = np.column_stack([_zero_mean(MIN_OBS, 0.01, 4), _zero_mean(MIN_OBS, 0.01, 5)])
    result = spa_test(panel, n_boot=200, seed=4, mean_block_length=1.0)
    assert result.n_models == MIN_MODELS


def test_zero_mean_panel_does_not_reject():
    panel = np.column_stack([_zero_mean(MIN_OBS * 2, 0.01, 6), _zero_mean(MIN_OBS * 2, 0.01, 7)])
    result = spa_test(panel, n_boot=400, seed=6, mean_block_length=1.0)
    assert (
        result.statistic == pytest.approx(0.0, abs=1e-8) or result.p_spa_consistent >= DEFAULT_ALPHA
    )
    assert result.passed is False


def test_strong_best_rejects_null():
    n = MIN_OBS * 2
    skill = np.full(n, 0.003) + _zero_mean(n, 0.008, 8) * 0.25
    noise = _zero_mean(n, 0.01, 9)
    result = spa_test(
        np.column_stack([skill, noise]),
        n_boot=400,
        seed=8,
        mean_block_length=1.0,
    )
    assert result.best_index == 0
    assert result.models[0].t_stat > result.models[1].t_stat
    assert result.p_spa_consistent < DEFAULT_ALPHA
    assert result.passed is True


def test_hansen_p_value_ordering():
    rng = np.random.default_rng(10)
    n = MIN_OBS * 2
    good = rng.normal(0.0015, 0.01, size=n)
    ok = rng.normal(0.0002, 0.01, size=n)
    bad = rng.normal(-0.004, 0.02, size=n)
    result = spa_test(
        np.column_stack([good, ok, bad]),
        n_boot=500,
        seed=10,
        mean_block_length=1.0,
    )
    assert result.p_spa_lower <= result.p_spa_consistent + 1e-12
    assert result.p_spa_consistent <= result.p_spa_upper + 1e-12


def test_same_seed_reproducible():
    n = MIN_OBS
    panel = np.column_stack([0.0008 + _zero_mean(n, 0.01, 11) * 0.5, _zero_mean(n, 0.01, 12)])
    a = spa_test(panel, n_boot=200, seed=99, mean_block_length=5.0)
    b = spa_test(panel, n_boot=200, seed=99, mean_block_length=5.0)
    assert a.p_spa_consistent == b.p_spa_consistent
    assert a.p_reality_check == b.p_reality_check
    assert a.statistic == b.statistic


def test_bartlett_white_noise_near_sigma2():
    rng = np.random.default_rng(13)
    x = rng.normal(0.0, 0.02, size=2000)
    var = bartlett_long_run_variance(x)
    assert var == pytest.approx(0.02**2, rel=0.25)


def test_too_many_models_fails_loud():
    panel = np.ones((MIN_OBS, 65)) * 0.001
    panel = panel + np.linspace(0, 1e-4, 65)
    with pytest.raises(SpaError, match="超过"):
        spa_test(panel, n_boot=200, seed=1)
