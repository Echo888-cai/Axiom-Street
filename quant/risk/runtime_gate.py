"""In-LEAN risk gate adapter (Phase 6 WP-1).

Reads LEAN duck-typed portfolio state and feeds the pure engine, which stays
free of LEAN objects. The source of this file is rendered into the container as
``risk_gate.py`` beside ``risk_engine.py`` (the pure engine source); the
import below resolves either the container sibling or, on the host, the
``quant.risk`` package — so the exact same file is exercised by host tests and
runs in LEAN.

``build_gate(base_cls, risk_json)`` returns a subclass of the user algorithm
that:
  - overrides ``OnData`` to run per-bar risk bookkeeping (drawdown halt,
    stop-loss exits) then forwards to the user's ``OnData``;
  - overrides ``SetHoldings`` to gate / shrink the intended target weight
    before the original order.
Warm-up bars are skipped. The gate only ever shrinks or holds an order — exits
always pass. Stop-loss is the one active exit, per the package decision.
"""

from __future__ import annotations

import json
from typing import Optional

try:  # container: sibling module written into the algorithm folder
    from risk_engine import RiskEngine  # type: ignore
except ImportError:  # host tests import this package normally
    from quant.risk.engine import RiskEngine  # type: ignore

_EPS = 1e-9


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _symbol_key(symbol) -> str:
    return getattr(symbol, "Value", symbol)


def _resolve_set_holdings(base_cls):
    """The nearest SetHoldings above the user class (normally QCAlgorithm)."""
    for cls in base_cls.__mro__:
        method = cls.__dict__.get("SetHoldings")
        if method is not None:
            return method
    raise AttributeError(f"{base_cls.__name__} 没有可调用的 SetHoldings")


def build_gate(base_cls, risk_json: str):
    """Return a ``<Name>RiskGated`` subclass enforcing ``risk_json`` limits."""
    limits = json.loads(risk_json)
    stop_loss = limits.get("stop_loss")
    stop_loss_by_symbol = limits.get("stop_loss_by_symbol") or {}
    name = f"{base_cls.__name__}RiskGated"
    base_on_data = getattr(base_cls, "OnData")
    base_set_holdings = _resolve_set_holdings(base_cls)

    def _state(self) -> dict:
        state = getattr(self, "_axiom_risk_state", None)
        if state is None:
            state = {
                "engine": RiskEngine(limits),
                "entries": {},
                "orders_this_bar": 0,
                "stop_exits_this_bar": set(),
            }
            object.__setattr__(self, "_axiom_risk_state", state)
        return state

    def _equity(self) -> float:
        try:
            return float(self.Portfolio.TotalPortfolioValue)
        except (AttributeError, TypeError):
            return 0.0

    def _symbol_qty(self, symbol) -> float:
        try:
            return _num(self.Securities[symbol].Holdings.Quantity)
        except (KeyError, AttributeError, TypeError):
            return 0.0

    def _symbol_price(self, symbol) -> Optional[float]:
        try:
            security = self.Securities[symbol]
            if not security.HasData:
                return None
            return float(security.Price)
        except (KeyError, AttributeError, TypeError):
            return None

    def _exposures(self) -> tuple[float, float]:
        gross = 0.0
        net = 0.0
        equity = _equity(self)
        if equity <= 0:
            return gross, net
        try:
            for _symbol, security in list(self.Securities.items()):
                try:
                    if not security.HasData:
                        continue
                    qty = _num(security.Holdings.Quantity)
                    if qty == 0:
                        continue
                    price = _num(security.Price)
                except AttributeError:
                    continue
                weight = qty * price / equity
                gross += abs(weight)
                net += weight
        except AttributeError:
            return 0.0, 0.0
        return gross, net

    def _stop_for(self, symbol) -> Optional[float]:
        named = stop_loss_by_symbol.get(_symbol_key(symbol))
        if named is not None:
            return float(named)
        return float(stop_loss) if stop_loss is not None else None

    def _record_entries(self) -> None:
        state = _state(self)
        entries = state["entries"]
        invested = set()
        for symbol, security in list(self.Securities.items()):
            try:
                qty = _num(security.Holdings.Quantity)
                has_data = bool(security.HasData)
            except AttributeError:
                continue
            if abs(qty) > _EPS and has_data:
                invested.add(symbol)
                if symbol not in entries:
                    try:
                        entry = security.Holdings.AveragePrice or security.Price
                    except AttributeError:
                        entry = None
                    if entry:
                        entries[symbol] = _num(entry)
        for symbol in list(entries):
            if symbol not in invested:
                del entries[symbol]

    def _run_stop_loss(self) -> None:
        state = _state(self)
        for symbol, entry_price in list(state["entries"].items()):
            stop = _stop_for(self, symbol)
            if stop is None or entry_price <= _EPS:
                continue
            price = _symbol_price(self, symbol)
            if price is None:
                continue
            if price / entry_price - 1.0 <= -abs(stop):
                if symbol not in state["stop_exits_this_bar"]:
                    state["stop_exits_this_bar"].add(symbol)
                    self.SetHoldings(symbol, 0.0)

    def gate_on_data(self, data) -> None:
        state = _state(self)
        if bool(getattr(self, "IsWarmingUp", False)):
            base_on_data(self, data)
            return
        state["engine"].on_bar(_equity(self))
        state["orders_this_bar"] = 0
        state["stop_exits_this_bar"] = set()
        # LEAN fills previous-bar orders before this OnData; reconcile the
        # stop-loss entries from realized holdings now.
        _record_entries(self)
        _run_stop_loss(self)
        base_on_data(self, data)

    def gate_set_holdings(self, symbol, weight, *args, **kwargs) -> None:
        state = _state(self)
        if bool(getattr(self, "IsWarmingUp", False)):
            base_set_holdings(self, symbol, weight, *args, **kwargs)
            return
        equity = _equity(self)
        if equity <= 0:
            return
        qty = _symbol_qty(self, symbol)
        price = _symbol_price(self, symbol)
        current_weight = qty * price / equity if price else 0.0
        gross, net = _exposures(self)
        intended = float(weight)
        decision = state["engine"].decide(
            symbol=_symbol_key(symbol),
            intended=intended,
            current=current_weight,
            gross=gross,
            net=net,
            orders_this_bar=state["orders_this_bar"],
        )
        sent = decision.allowed
        # Count increase-orders toward the per-bar budget (exits/reductions
        # always pass and are not counted).
        if abs(sent) > abs(current_weight) + _EPS:
            state["orders_this_bar"] += 1
        base_set_holdings(self, symbol, sent, *args, **kwargs)

    return type(
        name,
        (base_cls,),
        {
            "OnData": gate_on_data,
            "SetHoldings": gate_set_holdings,
            "_axiom_risk_record_entries": _record_entries,
            "_axiom_risk_run_stops": _run_stop_loss,
        },
    )
