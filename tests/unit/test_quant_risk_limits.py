"""Risk-limit config parsing (Phase 6 WP-1): fail-loud, permissive defaults."""

from __future__ import annotations

import pytest

from quant.risk.limits import parse_risk_limits
from quant.risk.types import RiskLimits


def test_empty_block_is_permissive() -> None:
    limits = parse_risk_limits({})
    assert isinstance(limits, RiskLimits)
    assert limits.max_position_pct is None
    assert limits.stop_loss is None
    assert limits.can_alter_order() is False


def test_single_cap_binds() -> None:
    limits = parse_risk_limits({"max_position_pct": 0.5})
    assert limits.max_position_pct == 0.5
    assert limits.can_alter_order() is True


def test_full_block_parses() -> None:
    limits = parse_risk_limits(
        {
            "max_position_pct": 0.3,
            "max_position_pct_by_symbol": {"SPY": 0.5},
            "max_gross_leverage": 1.5,
            "max_net_leverage": 1.0,
            "max_concentration_pct": 0.4,
            "stop_loss": 0.05,
            "stop_loss_by_symbol": {"QQQ": 0.03},
            "portfolio_drawdown_halt": 0.15,
            "circuit_breaker_bars": 5,
            "max_orders_per_bar": 3,
        }
    )
    assert limits.max_position_pct_by_symbol == {"SPY": 0.5}
    assert limits.stop_loss_by_symbol == {"QQQ": 0.03}
    assert limits.circuit_breaker_bars == 5
    assert limits.can_alter_order() is True
    serialized = limits.to_dict()
    assert serialized["max_position_pct"] == 0.3
    assert serialized["stop_loss_by_symbol"] == {"QQQ": 0.03}


@pytest.mark.parametrize(
    "block",
    [
        {"unknown_key": 0.1},
        {"max_position_pct": -0.5},
        {"stop_loss": float("nan")},
        {"portfolio_drawdown_halt": float("inf")},
        {"circuit_breaker_bars": 2.5},
        {"max_orders_per_bar": -1},
        {"max_position_pct_by_symbol": "SPY:0.1"},
        {"stop_loss_by_symbol": {"SPY": -0.1}},
        {"max_position_pct_by_symbol": {"": 0.1}},
    ],
)
def test_invalid_blocks_fail_loud(block: dict) -> None:
    with pytest.raises(ValueError, match="risk_limits"):
        parse_risk_limits(block)


def test_none_values_are_ignored() -> None:
    limits = parse_risk_limits({"max_position_pct": None, "stop_loss": None})
    assert limits.can_alter_order() is False


def test_non_object_block_fails() -> None:
    with pytest.raises(ValueError, match="risk_limits"):
        parse_risk_limits(["max_position_pct"])  # type: ignore[arg-type]
