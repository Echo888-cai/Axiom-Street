"""Cost-curve breakeven — interpolation and pass/fail against realistic bps."""

from __future__ import annotations

import pytest

from quant.validation.cost import (
    CostSensitivityError,
    assert_cost_paths_differ,
    classify_cost_curve,
    interpolate_breakeven,
)


def test_interpolates_zero_crossing():
    bps, kind = interpolate_breakeven([0.0, 5.0, 10.0, 20.0], [0.05, 0.03, 0.01, -0.01])
    assert kind == "interpolated"
    assert bps == pytest.approx(15.0)


def test_zero_cost_already_dead():
    bps, kind = interpolate_breakeven([0.0, 5.0, 10.0], [-0.01, -0.02, -0.03])
    assert kind == "nonpositive_at_floor"
    assert bps == 0.0


def test_positive_floor_already_dead_fails_loud():
    with pytest.raises(CostSensitivityError, match="0 bps"):
        interpolate_breakeven([5.0, 10.0, 20.0], [-0.01, -0.02, -0.03])


def test_above_grid_has_no_breakeven():
    bps, kind = interpolate_breakeven([0.0, 5.0, 10.0], [0.04, 0.03, 0.01])
    assert kind == "above_grid"
    assert bps is None


def test_refuses_to_extrapolate_outside_bracket():
    with pytest.raises(CostSensitivityError, match="严格递增"):
        interpolate_breakeven([10.0, 5.0], [0.02, -0.01])


def test_dies_at_or_below_realistic_cost():
    result = classify_cost_curve(
        [0.0, 5.0, 10.0],
        [0.02, 0.0, -0.02],
        realistic_one_way_bps=5.0,
    )
    assert result.passed is False
    assert result.breakeven_bps == pytest.approx(5.0)
    assert "判死" in result.reason
    assert "5.00 bps" in result.conclusion


def test_survives_when_breakeven_above_realistic():
    result = classify_cost_curve(
        [0.0, 5.0, 10.0, 20.0],
        [0.04, 0.03, 0.02, -0.02],
        realistic_one_way_bps=5.0,
    )
    assert result.passed is True
    assert result.breakeven_bps == pytest.approx(15.0)
    assert "15.00 bps" in result.conclusion


def test_grid_ceiling_is_a_pass_not_an_invented_number():
    result = classify_cost_curve(
        [0.0, 5.0, 50.0],
        [0.05, 0.04, 0.01],
        realistic_one_way_bps=5.0,
    )
    assert result.passed is True
    assert result.breakeven_bps is None
    assert result.breakeven_kind == "above_grid"
    assert "网格上限" in result.conclusion


def test_missing_alpha_fails_loud():
    with pytest.raises(CostSensitivityError, match="缺失"):
        classify_cost_curve([0.0, 5.0, 10.0], [0.02, None, -0.01])


def test_identical_paths_fail_when_traded():
    with pytest.raises(CostSensitivityError, match="slippage_bps"):
        assert_cost_paths_differ([100_000.0, 100_000.0, 100_000.0], traded=True)


def test_identical_paths_ok_when_never_traded():
    assert_cost_paths_differ([100_000.0, 100_000.0, 100_000.0], traded=False)
