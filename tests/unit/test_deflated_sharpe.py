"""Bailey & López de Prado (2014) DSR — literature known values."""

from __future__ import annotations

import math

import pytest

from quant.metrics.deflated_sharpe import (
    DSR_PASS_THRESHOLD,
    annualized_to_per_period,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    pearson_kurtosis,
    trials_stdev_from_sharpes,
)

# Paper example (Bailey & López de Prado 2014, “A numerical example”):
# annualized SR̂ = 2.5, T = 1250, V[{SR}] = 1/2, γ3 = −3, γ4 = 10, 250 obs/year.
_PPY = 250.0
_SR = annualized_to_per_period(2.5, _PPY)
_STD = math.sqrt(0.5) / math.sqrt(_PPY)


def test_paper_example_n100_is_not_significant():
    result = deflated_sharpe_ratio(_SR, 1250, 100, _STD, skewness=-3.0, kurtosis=10.0)
    assert result.dsr == pytest.approx(0.9004, abs=5e-4)
    assert result.passed is False
    assert result.psr > 0.99  # non-normality-only PSR still looks great


def test_paper_example_n46_crosses_95():
    result = deflated_sharpe_ratio(_SR, 1250, 46, _STD, skewness=-3.0, kurtosis=10.0)
    assert result.dsr == pytest.approx(0.9505, abs=5e-4)
    assert result.passed is True


def test_paper_example_normal_returns_allows_n88():
    result = deflated_sharpe_ratio(_SR, 1250, 88, _STD, skewness=0.0, kurtosis=3.0)
    assert result.dsr == pytest.approx(0.9505, abs=5e-4)


def test_n1_equals_psr_against_zero():
    result = deflated_sharpe_ratio(0.1, 500, 1, 0.0, skewness=0.0, kurtosis=3.0)
    assert result.sr_star == 0.0
    assert result.dsr == pytest.approx(result.psr)
    assert result.dsr > 0.5


def test_more_trials_deflates_dsr():
    a = deflated_sharpe_ratio(_SR, 1250, 10, _STD, skewness=-3.0, kurtosis=10.0)
    b = deflated_sharpe_ratio(_SR, 1250, 200, _STD, skewness=-3.0, kurtosis=10.0)
    assert b.dsr < a.dsr
    assert b.sr_star > a.sr_star


def test_expected_max_grows_with_n():
    assert expected_max_sharpe(10, 0.2) < expected_max_sharpe(100, 0.2)


def test_refuse_non_positive_kurtosis():
    with pytest.raises(ValueError, match="Pearson"):
        deflated_sharpe_ratio(0.1, 100, 1, 0.0, kurtosis=0.0)


def test_pearson_from_pandas_excess():
    assert pearson_kurtosis(0.0) == 3.0
    assert pearson_kurtosis(7.0) == 10.0


def test_trials_stdev_single_is_zero():
    assert trials_stdev_from_sharpes([1.2]) == 0.0
    assert trials_stdev_from_sharpes([1.0, 1.0, 1.0]) == 0.0


def test_pass_threshold_is_paper_95():
    assert DSR_PASS_THRESHOLD == 0.95
