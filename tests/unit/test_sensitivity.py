"""Knife-edge vs plateau classification — known-shape grids."""

from __future__ import annotations

import pytest

from quant.metrics.pbo import strategy_reads_parameter
from quant.strategy_sdk.spy_200dma import DEFAULT_STRATEGY_CODE
from quant.validation.sensitivity import (
    SensitivityError,
    assert_navs_differ,
    classify_surface,
)


def test_isolated_peak_is_knife_edge():
    result = classify_surface([100, 150, 200, 250, 300], [0.2, 0.3, 2.0, 0.25, 0.2])
    assert result.shape == "knife_edge"
    assert result.passed is False
    assert result.plateau_width == 1
    assert result.peak_value == 200
    assert result.neighbor_drop == pytest.approx(1.75)


def test_wide_ridge_is_plateau():
    result = classify_surface([100, 150, 200, 250, 300], [1.20, 1.35, 1.40, 1.32, 1.18])
    assert result.shape == "plateau"
    assert result.passed is True
    assert result.plateau_width >= 3
    assert result.peak_value == 200
    assert sum(1 for p in result.points if p.on_plateau) == result.plateau_width


def test_two_point_ridge_is_still_knife_edge():
    result = classify_surface([100, 150, 200, 250, 300], [0.1, 1.4, 1.5, 0.2, 0.1])
    assert result.shape == "knife_edge"
    assert result.passed is False
    assert result.plateau_width == 2


def test_flat_positive_ridge_is_plateau():
    result = classify_surface([100, 150, 200, 250], [1.1, 1.1, 1.1, 1.1])
    assert result.shape == "plateau"
    assert result.passed is True
    assert result.peak_value == 200
    assert result.plateau_width == 4


def test_nonpositive_peak_fails():
    result = classify_surface([100, 150, 200], [-0.4, 0.0, -0.2])
    assert result.passed is False
    assert "≤ 0" in result.reason


def test_missing_sharpe_fails_loud():
    with pytest.raises(SensitivityError, match="缺失"):
        classify_surface([100, 150, 200], [1.0, None, 0.9])


def test_too_few_points_fails_loud():
    with pytest.raises(SensitivityError, match="至少需要 3"):
        classify_surface([100, 200], [1.0, 1.1])


def test_duplicate_values_fail_loud():
    with pytest.raises(SensitivityError, match="互异"):
        classify_surface([100, 100, 200], [1.0, 1.1, 1.2])


def test_identical_equity_fails_loud():
    with pytest.raises(SensitivityError, match="无法区分"):
        assert_navs_differ([100_000.0, 100_000.0, 100_000.0])


def test_unsorted_input_still_classifies_by_value():
    result = classify_surface([300, 100, 200], [0.2, 0.2, 2.0])
    assert result.peak_value == 200
    assert [p.value for p in result.points] == [100, 200, 300]


def test_default_template_reads_lookback():
    assert strategy_reads_parameter(DEFAULT_STRATEGY_CODE, "lookback")
    assert strategy_reads_parameter(DEFAULT_STRATEGY_CODE, "slippage_bps")
    assert strategy_reads_parameter(DEFAULT_STRATEGY_CODE, "fee_usd")
    assert not strategy_reads_parameter(DEFAULT_STRATEGY_CODE, "not_a_param")
    assert not strategy_reads_parameter('GetParameter("lookback")', 'look"back')
