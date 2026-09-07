"""Pure risk engine decisions (Phase 6 WP-1): caps, leverage, halt, budget."""

from __future__ import annotations

import pytest

from quant.risk.engine import RiskEngine


def test_position_cap_reduces_oversized_intent() -> None:
    engine = RiskEngine({"max_position_pct": 0.5})
    decision = engine.decide(
        symbol="SPY", intended=0.8, current=0.0, gross=0.0, net=0.0, orders_this_bar=0
    )
    assert decision.allowed == 0.5
    assert "position_cap" in (decision.reason or "")


def test_position_cap_exact_equal_passes() -> None:
    engine = RiskEngine({"max_position_pct": 0.5})
    decision = engine.decide(
        symbol="SPY", intended=0.5, current=0.0, gross=0.0, net=0.0, orders_this_bar=0
    )
    assert decision.allowed == 0.5
    assert decision.reason is None


def test_per_symbol_cap_overrides_global() -> None:
    engine = RiskEngine({"max_position_pct": 0.5, "max_position_pct_by_symbol": {"SPY": 0.2}})
    decision = engine.decide(
        symbol="SPY", intended=0.4, current=0.0, gross=0.0, net=0.0, orders_this_bar=0
    )
    assert decision.allowed == 0.2
    other = engine.decide(
        symbol="QQQ", intended=0.4, current=0.0, gross=0.0, net=0.0, orders_this_bar=0
    )
    assert other.allowed == 0.4


def test_concentration_cap_binds() -> None:
    engine = RiskEngine({"max_concentration_pct": 0.25})
    decision = engine.decide(
        symbol="A", intended=0.4, current=0.0, gross=0.0, net=0.0, orders_this_bar=0
    )
    assert decision.allowed == 0.25
    assert "concentration_cap" in (decision.reason or "")


def test_gross_leverage_caps_intent() -> None:
    engine = RiskEngine({"max_gross_leverage": 1.0})
    # gross currently 0.9; adding 0.3 of a fresh name would exceed 1.0.
    decision = engine.decide(
        symbol="A", intended=0.3, current=0.0, gross=0.9, net=0.9, orders_this_bar=0
    )
    assert decision.allowed == pytest.approx(0.1)
    assert "gross_leverage" in (decision.reason or "")


def test_net_leverage_caps_short() -> None:
    engine = RiskEngine({"max_net_leverage": 1.0})
    # net currently -0.8 (short book); a new short of 0.4 would make -1.2.
    decision = engine.decide(
        symbol="B", intended=-0.4, current=0.0, gross=0.8, net=-0.8, orders_this_bar=0
    )
    assert decision.allowed == pytest.approx(-0.2)
    assert "net_leverage" in (decision.reason or "")


def test_drawdown_halt_blocks_increases_only() -> None:
    engine = RiskEngine({"portfolio_drawdown_halt": 0.1})
    engine.on_bar(100.0)
    engine.on_bar(85.0)  # -15% from peak -> halted
    increase = engine.decide(
        symbol="SPY", intended=0.5, current=0.1, gross=0.1, net=0.1, orders_this_bar=0
    )
    assert increase.allowed == pytest.approx(0.1)
    assert "drawdown_halt" in (increase.reason or "")
    # Exits always pass.
    exit_decision = engine.decide(
        symbol="SPY", intended=0.0, current=0.1, gross=0.1, net=0.1, orders_this_bar=0
    )
    assert exit_decision.allowed == 0.0


def test_halt_releases_on_new_high() -> None:
    engine = RiskEngine({"portfolio_drawdown_halt": 0.1})
    engine.on_bar(100.0)
    engine.on_bar(80.0)  # halted
    engine.on_bar(110.0)  # new high resets
    decision = engine.decide(
        symbol="SPY", intended=0.5, current=0.0, gross=0.0, net=0.0, orders_this_bar=0
    )
    assert decision.allowed == 0.5
    assert decision.reason is None


def test_circuit_breaker_releases_after_bars() -> None:
    engine = RiskEngine({"portfolio_drawdown_halt": 0.1, "circuit_breaker_bars": 3})
    engine.on_bar(100.0)
    engine.on_bar(80.0)  # breach -> halted (step 2)
    engine.on_bar(79.0)  # still breached, step 3
    blocked = engine.decide(
        symbol="A", intended=0.4, current=0.0, gross=0.0, net=0.0, orders_this_bar=0
    )
    assert "drawdown_halt" in (blocked.reason or "")
    engine.on_bar(79.0)  # step 4 -> (4 - 2) = 2 < 3 still halted
    engine.on_bar(79.0)  # step 5 -> (5-2)=3 >= 3 release
    freed = engine.decide(
        symbol="A", intended=0.4, current=0.0, gross=0.0, net=0.0, orders_this_bar=0
    )
    assert freed.allowed == 0.4


def test_order_budget_blocks_increases_after_limit() -> None:
    engine = RiskEngine({"max_orders_per_bar": 1})
    first = engine.decide(
        symbol="A", intended=0.3, current=0.0, gross=0.0, net=0.0, orders_this_bar=0
    )
    assert first.allowed == 0.3
    second = engine.decide(
        symbol="B", intended=0.3, current=0.0, gross=0.0, net=0.0, orders_this_bar=1
    )
    assert second.allowed == 0.0
    assert "order_budget" in (second.reason or "")
    # Exits are never blocked by the budget.
    exit_decision = engine.decide(
        symbol="B", intended=0.0, current=0.3, gross=0.3, net=0.3, orders_this_bar=1
    )
    assert exit_decision.allowed == 0.0


def test_non_finite_intent_fails_loud() -> None:
    engine = RiskEngine({})
    with pytest.raises(ValueError):
        engine.decide(
            symbol="A", intended=float("nan"), current=0.0, gross=0.0, net=0.0, orders_this_bar=0
        )


def test_risk_engine_from_json_round_trip() -> None:
    from quant.risk.engine import risk_engine_from_json

    engine = risk_engine_from_json('{"max_position_pct": 0.5}')
    decision = engine.decide(
        symbol="A", intended=0.9, current=0.0, gross=0.0, net=0.0, orders_this_bar=0
    )
    assert decision.allowed == 0.5
