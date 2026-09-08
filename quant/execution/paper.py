"""Pure paper-execution rules.

This module has no service, database, or broker imports. It validates the
simulation command, reconstructs long-only positions from fills, and adapts
the existing pure risk engine to quantity-based paper orders.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping

from quant.risk.engine import RiskEngine

_EPS = 1e-12


def _finite_positive(value: float, field: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{field} must be a finite positive number")
    return number


@dataclass(frozen=True)
class PaperOrderCommand:
    symbol: str
    side: str
    quantity: float
    simulation_price: float
    client_order_id: str

    def __post_init__(self) -> None:
        symbol = str(self.symbol).strip().upper()
        side = str(self.side).strip().upper()
        client_order_id = str(self.client_order_id).strip()
        if not symbol:
            raise ValueError("symbol must not be empty")
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if not client_order_id:
            raise ValueError("client_order_id must not be empty")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "client_order_id", client_order_id)
        object.__setattr__(self, "quantity", _finite_positive(self.quantity, "quantity"))
        object.__setattr__(
            self,
            "simulation_price",
            _finite_positive(self.simulation_price, "simulation_price"),
        )


@dataclass(frozen=True)
class FillRecord:
    symbol: str
    side: str
    quantity: float
    price: float

    def __post_init__(self) -> None:
        symbol = str(self.symbol).strip().upper()
        side = str(self.side).strip().upper()
        if not symbol:
            raise ValueError("symbol must not be empty")
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "quantity", _finite_positive(self.quantity, "quantity"))
        object.__setattr__(self, "price", _finite_positive(self.price, "price"))


@dataclass
class PositionState:
    quantity: float
    average_price: float
    realized_pnl: float
    mark_price: float


@dataclass(frozen=True)
class RiskTarget:
    allowed_quantity: float
    current_weight: float
    intended_weight: float
    allowed_weight: float
    reason: str | None = None


def rebuild_positions(fills: Iterable[FillRecord]) -> dict[str, PositionState]:
    positions: dict[str, PositionState] = {}
    for fill in fills:
        position = positions.setdefault(fill.symbol, PositionState(0.0, 0.0, 0.0, fill.price))
        if fill.side == "BUY":
            new_quantity = position.quantity + fill.quantity
            position.average_price = (
                position.quantity * position.average_price + fill.quantity * fill.price
            ) / new_quantity
            position.quantity = new_quantity
        else:
            if fill.quantity > position.quantity + _EPS:
                raise ValueError(
                    f"cannot sell {fill.quantity} {fill.symbol}; only {position.quantity} held"
                )
            position.realized_pnl += (fill.price - position.average_price) * fill.quantity
            position.quantity -= fill.quantity
            if abs(position.quantity) <= _EPS:
                position.quantity = 0.0
                position.average_price = 0.0
        position.mark_price = fill.price
    return {symbol: position for symbol, position in positions.items() if position.quantity > _EPS}


def risk_target(
    *,
    symbol: str,
    side: str,
    quantity: float,
    simulation_price: float,
    account_equity: float,
    position: PositionState,
    gross_exposure: float,
    net_exposure: float,
    orders_this_bar: int,
    risk_limits: Mapping[str, object],
) -> RiskTarget:
    side = str(side).strip().upper()
    requested = _finite_positive(quantity, "quantity")
    price = _finite_positive(simulation_price, "simulation_price")
    equity = _finite_positive(account_equity, "account_equity")
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    if side == "SELL" and requested > position.quantity + _EPS:
        raise ValueError(f"cannot sell {requested} {position.quantity} held")

    current_weight = position.quantity * price / equity
    signed_delta = requested if side == "BUY" else -requested
    intended_weight = (position.quantity + signed_delta) * price / equity
    engine = RiskEngine(dict(risk_limits))
    engine.on_bar(equity)
    decision = engine.decide(
        symbol=str(symbol).strip().upper(),
        intended=intended_weight,
        current=current_weight,
        gross=float(gross_exposure),
        net=float(net_exposure),
        orders_this_bar=int(orders_this_bar),
    )
    allowed_quantity = abs(decision.allowed - current_weight) * equity / price
    if side == "SELL":
        allowed_quantity = min(allowed_quantity, requested)
    else:
        allowed_quantity = min(allowed_quantity, requested)
    return RiskTarget(
        allowed_quantity=0.0 if allowed_quantity <= _EPS else allowed_quantity,
        current_weight=current_weight,
        intended_weight=intended_weight,
        allowed_weight=decision.allowed,
        reason=decision.reason,
    )
