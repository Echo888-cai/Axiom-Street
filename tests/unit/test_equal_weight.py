"""Equal-weight cross-section sizing and LEAN template contract."""

from __future__ import annotations

import pytest

from quant.engine.base import BacktestRequest
from quant.engine.lean import lean_runtime_parameters
from quant.strategy_sdk.equal_weight import (
    DEFAULT_EQUAL_WEIGHT_CLASS,
    DEFAULT_EQUAL_WEIGHT_CODE,
    DEFAULT_EQUAL_WEIGHT_UNIVERSE,
    equal_weight_builder_config,
    equal_weight_targets,
    parse_universe_parameter,
)


def test_ten_name_equal_weight_sums_to_one():
    weights = equal_weight_targets(DEFAULT_EQUAL_WEIGHT_UNIVERSE)
    assert list(weights) == DEFAULT_EQUAL_WEIGHT_UNIVERSE
    assert len(weights) == 10
    assert abs(sum(weights.values()) - 1.0) < 1e-12
    assert all(abs(value - 0.1) < 1e-12 for value in weights.values())


def test_equal_weight_empty_fails_loud():
    with pytest.raises(ValueError, match="至少需要一个标的"):
        equal_weight_targets([])


def test_parse_universe_parameter():
    assert parse_universe_parameter("spy, qqq;IWM") == ["SPY", "QQQ", "IWM"]
    with pytest.raises(ValueError, match="empty"):
        parse_universe_parameter("  ")


def test_lean_algorithm_string_requires_universe_parameter():
    assert "class EqualWeightUniverseAlgorithm" in DEFAULT_EQUAL_WEIGHT_CODE
    assert 'self.GetParameter("universe")' in DEFAULT_EQUAL_WEIGHT_CODE
    assert "AfterMarketClose" not in DEFAULT_EQUAL_WEIGHT_CODE
    assert equal_weight_builder_config()["class_name"] == DEFAULT_EQUAL_WEIGHT_CLASS


def test_lean_runtime_parameters_include_universe():
    from datetime import date

    request = BacktestRequest(
        backtest_id="bt-1",
        strategy_code="pass",
        strategy_class_name=DEFAULT_EQUAL_WEIGHT_CLASS,
        start_date=date(2018, 1, 1),
        end_date=date(2018, 6, 1),
        benchmark="SPY",
        initial_capital=100_000,
        universe=list(DEFAULT_EQUAL_WEIGHT_UNIVERSE),
    )
    params = lean_runtime_parameters(request)
    assert params["universe"] == ",".join(DEFAULT_EQUAL_WEIGHT_UNIVERSE)
    assert params["start_date"] == "2018-01-01"


def test_lean_runtime_parameters_empty_universe_fails():
    from datetime import date

    request = BacktestRequest(
        backtest_id="bt-1",
        strategy_code="pass",
        strategy_class_name="X",
        start_date=date(2018, 1, 1),
        end_date=date(2018, 6, 1),
        benchmark="SPY",
        initial_capital=100_000,
        universe=[],
    )
    with pytest.raises(ValueError, match="at least one symbol"):
        lean_runtime_parameters(request)
