"""Risk-limit configuration model (host side, Phase 6 WP-1).

Stdlib-only so the whole ``quant/risk`` tree stays safe to render into the
LEAN container. The engine itself (``engine.py``) reads a plain serialized
dict; this model validates the human/UI-facing block and serializes to it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RiskLimits:
    """Hard risk limits. ``None`` / empty means that gate is not enforced."""

    max_position_pct: Optional[float] = None
    max_position_pct_by_symbol: dict[str, float] = field(default_factory=dict)
    max_gross_leverage: Optional[float] = None
    max_net_leverage: Optional[float] = None
    max_concentration_pct: Optional[float] = None
    stop_loss: Optional[float] = None
    stop_loss_by_symbol: dict[str, float] = field(default_factory=dict)
    portfolio_drawdown_halt: Optional[float] = None
    circuit_breaker_bars: Optional[int] = None
    max_orders_per_bar: Optional[int] = None

    def to_dict(self) -> dict:
        """JSON-safe serialization consumed by the engine / adapter."""
        return {
            "max_position_pct": self.max_position_pct,
            "max_position_pct_by_symbol": dict(self.max_position_pct_by_symbol),
            "max_gross_leverage": self.max_gross_leverage,
            "max_net_leverage": self.max_net_leverage,
            "max_concentration_pct": self.max_concentration_pct,
            "stop_loss": self.stop_loss,
            "stop_loss_by_symbol": dict(self.stop_loss_by_symbol),
            "portfolio_drawdown_halt": self.portfolio_drawdown_halt,
            "circuit_breaker_bars": self.circuit_breaker_bars,
            "max_orders_per_bar": self.max_orders_per_bar,
        }

    def can_alter_order(self) -> bool:
        """True when any hard limit could bind an order (else: pure pass-through)."""
        if self.max_position_pct is not None:
            return True
        if self.max_position_pct_by_symbol:
            return True
        if self.max_gross_leverage is not None:
            return True
        if self.max_net_leverage is not None:
            return True
        if self.max_concentration_pct is not None:
            return True
        if self.stop_loss is not None:
            return True
        if self.stop_loss_by_symbol:
            return True
        if self.portfolio_drawdown_halt is not None:
            return True
        if self.circuit_breaker_bars is not None:
            return True
        if self.max_orders_per_bar is not None:
            return True
        return False
