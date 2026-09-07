"""Pure, self-contained risk engine (Phase 6 WP-1).

This module is deliberately import-free beyond the Python stdlib so its source
can be rendered verbatim into the LEAN container (``algo_dir/risk_engine.py``)
and run there identically to how the host tests it. It never touches LEAN
objects or ``quant.*``: the thin LEAN adapter (``runtime_gate.py``) reads
portfolio state and feeds plain numbers here.

All weights/exposures are *fractions of portfolio equity* (signed; shorts are
negative). A limit that is ``None`` is not enforced (permissive).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class Decision:
    """Outcome of gating one intended target weight.

    ``allowed`` is the weight the order should actually target (<= |intended|
    when a limit binds). ``reason`` is a stable code or None when unchanged.
    """

    allowed: float
    reason: Optional[str] = None


class RiskEngine:
    """Stateful risk gate over a stream of intended target weights.

    State lives per run: tracked portfolio-equity peak (for the drawdown
    halt) and a circuit-breaker release counter. The per-bar order budget is
    owned by the caller (the adapter), which only counts orders it actually
    places; ``decide`` receives that count and vetoes further change orders
    once the budget is spent.
    """

    def __init__(self, limits: dict) -> None:
        self.max_position_pct = _float_or_none(limits.get("max_position_pct"))
        self.max_position_pct_by_symbol = _float_map(limits.get("max_position_pct_by_symbol"))
        self.max_gross_leverage = _float_or_none(limits.get("max_gross_leverage"))
        self.max_net_leverage = _float_or_none(limits.get("max_net_leverage"))
        self.max_concentration_pct = _float_or_none(limits.get("max_concentration_pct"))
        self.portfolio_drawdown_halt = _float_or_none(limits.get("portfolio_drawdown_halt"))
        self.circuit_breaker_bars = _int_or_none(limits.get("circuit_breaker_bars"))
        self.max_orders_per_bar = _int_or_none(limits.get("max_orders_per_bar"))

        self._peak_equity: Optional[float] = None
        self._halted = False
        self._halt_since: Optional[int] = None
        self._step = 0

    # ------------------------------------------------------------ per-bar hook

    def on_bar(self, equity: float) -> None:
        """Advance one bar with the current portfolio equity.

        Tracks the equity peak; on a drawdown breach of
        ``portfolio_drawdown_halt`` sets the halt flag (blocks new/increased
        exposure). The halt releases on a new equity high, or after
        ``circuit_breaker_bars`` bars since the breach when configured.
        """
        self._step += 1
        equity = float(equity)
        peak = self._peak_equity

        if peak is None or equity >= peak:
            self._peak_equity = equity
            self._halted = False
            self._halt_since = None
            return

        drawdown = equity / peak - 1.0  # negative
        halt_threshold = self.portfolio_drawdown_halt
        breaker = self.circuit_breaker_bars
        breached = halt_threshold is not None and drawdown <= -abs(halt_threshold)
        if breached:
            if not self._halted:
                self._halted = True
                self._halt_since = self._step
            elif breaker is not None and (self._step - (self._halt_since or self._step)) >= breaker:
                self._halted = False
        elif (
            self._halted
            and breaker is not None
            and (self._step - (self._halt_since or self._step)) >= breaker
        ):
            self._halted = False

    # --------------------------------------------------------------- decision

    def decide(
        self,
        *,
        symbol: str,
        intended: float,
        current: float,
        gross: float,
        net: float,
        orders_this_bar: int,
    ) -> Decision:
        """Return the allowed weight for one intended target-weight order.

        ``gross`` / ``net`` are the portfolio's current gross / net exposure as
        fractions of equity (before this order); ``orders_this_bar`` is how many
        change-orders this bar already placed. Exits always pass; the gate only
        ever shrinks or holds an order, never forcing a change bigger than the
        strategy asked for (the drawdown halt is a passive gate).
        """
        intended = float(intended)
        current = float(current)
        if not _finite(intended):
            raise ValueError("intended weight must be finite")
        if not _finite(gross) or not _finite(net):
            raise ValueError("gross/net exposure must be finite")

        allowed = intended
        reasons: list[str] = []

        cap = self._symbol_cap(symbol)
        if cap is not None and abs(allowed) > cap:
            allowed = _sign(allowed) * cap
            reasons.append("position_cap")

        concentration = self.max_concentration_pct
        if concentration is not None and abs(allowed) > concentration:
            allowed = _sign(allowed) * concentration
            reasons.append("concentration_cap")

        proposed_gross = gross - abs(current) + abs(allowed)
        max_gross = self.max_gross_leverage
        if max_gross is not None and proposed_gross > max_gross:
            budget = max_gross - gross + abs(current)
            allowed = _sign(allowed) * min(abs(allowed), max(budget, 0.0))
            reasons.append("gross_leverage")

        proposed_net = net - current + allowed
        max_net = self.max_net_leverage
        if max_net is not None:
            if proposed_net > max_net:
                allowed = min(allowed, max_net - net + current)
                reasons.append("net_leverage")
            elif proposed_net < -max_net:
                allowed = max(allowed, -max_net - net + current)
                reasons.append("net_leverage")

        # Drawdown halt: block only increases; exits always pass.
        if self._halted and abs(allowed) > abs(current) + _EPS:
            allowed = current
            reasons.append("drawdown_halt")

        # Per-bar order budget: like the halt, it only blocks increased
        # exposure — exits and reductions always pass.
        if (
            self.max_orders_per_bar is not None
            and orders_this_bar >= self.max_orders_per_bar
            and abs(allowed) > abs(current) + _EPS
        ):
            allowed = current
            reasons.append("order_budget")

        if abs(allowed - intended) > _EPS:
            return Decision(allowed=_clamp(allowed), reason=",".join(reasons))
        return Decision(allowed=intended)

    def _symbol_cap(self, symbol: str) -> Optional[float]:
        named = self.max_position_pct_by_symbol.get(symbol)
        if named is not None:
            return named
        return self.max_position_pct


# ----------------------------------------------------------------- helpers

_EPS = 1e-12


def _sign(value: float) -> float:
    return -1.0 if value < 0 else 1.0


def _clamp(value: float) -> float:
    if not _finite(value):
        return 0.0
    return value


def _finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


def _float_or_none(value) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _int_or_none(value) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def _float_map(value) -> dict[str, float]:
    if not value:
        return {}
    return {str(key): float(item) for key, item in value.items()}


def risk_engine_from_json(payload: str) -> RiskEngine:
    """Host/container shared constructor from the serialized limits JSON."""
    return RiskEngine(json.loads(payload))
