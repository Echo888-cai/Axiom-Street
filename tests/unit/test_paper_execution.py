"""Pure paper execution rules (E6-1)."""

from __future__ import annotations

import pytest

from quant.execution.paper import (
    FillRecord,
    PaperOrderCommand,
    PositionState,
    rebuild_positions,
    risk_target,
)


def test_order_command_normalizes_symbol_and_rejects_invalid_numbers() -> None:
    command = PaperOrderCommand(
        symbol=" spy ",
        side="buy",
        quantity=2,
        simulation_price=100,
        client_order_id=" paper-1 ",
    )

    assert command.symbol == "SPY"
    assert command.side == "BUY"
    assert command.client_order_id == "paper-1"

    with pytest.raises(ValueError, match="quantity"):
        PaperOrderCommand("SPY", "BUY", 0, 100, "paper-2")
    with pytest.raises(ValueError, match="simulation_price"):
        PaperOrderCommand("SPY", "BUY", 1, float("nan"), "paper-3")


def test_rebuild_positions_applies_buys_and_sells_with_realized_pnl() -> None:
    positions = rebuild_positions(
        [
            FillRecord("SPY", "BUY", 10, 100),
            FillRecord("SPY", "BUY", 10, 110),
            FillRecord("SPY", "SELL", 5, 130),
        ]
    )

    assert positions["SPY"] == PositionState(
        quantity=15, average_price=105, realized_pnl=125, mark_price=130
    )


def test_rebuild_positions_fails_loud_on_oversell() -> None:
    with pytest.raises(ValueError, match="cannot sell"):
        rebuild_positions([FillRecord("SPY", "SELL", 1, 100)])


def test_risk_target_shrinks_buy_to_position_cap() -> None:
    result = risk_target(
        symbol="SPY",
        side="BUY",
        quantity=10,
        simulation_price=100,
        account_equity=1_000,
        position=PositionState(quantity=0, average_price=0, realized_pnl=0, mark_price=100),
        gross_exposure=0,
        net_exposure=0,
        orders_this_bar=0,
        risk_limits={"max_position_pct": 0.5},
    )

    assert result.allowed_quantity == 5
    assert result.reason == "position_cap"


def test_risk_target_rejects_sell_beyond_existing_long() -> None:
    with pytest.raises(ValueError, match="cannot sell"):
        risk_target(
            symbol="SPY",
            side="SELL",
            quantity=2,
            simulation_price=100,
            account_equity=1_000,
            position=PositionState(quantity=1, average_price=100, realized_pnl=0, mark_price=100),
            gross_exposure=0.1,
            net_exposure=0.1,
            orders_this_bar=0,
            risk_limits={},
        )
