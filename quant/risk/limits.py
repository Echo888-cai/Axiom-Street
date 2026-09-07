"""Fail-loud parsing of the optional ``config["risk_limits"]`` block (WP-1).

The legacy ``config["risk"]`` block stays inert display metadata (e.g.
equal_weight stores ``max_position_pct = 1/N`` as a *sizing* hint that would be
wrong to enforce as a hard per-symbol cap). Hard limits are read only from the
new, explicit ``risk_limits`` block; unknown keys and malformed values raise so
a misconfigured run fails before it reaches the engine, never degrades.
"""

from __future__ import annotations

import math

from quant.risk.types import RiskLimits

_NUMERIC_KEYS = (
    "max_position_pct",
    "max_gross_leverage",
    "max_net_leverage",
    "max_concentration_pct",
    "stop_loss",
    "portfolio_drawdown_halt",
)
_INT_KEYS = ("circuit_breaker_bars", "max_orders_per_bar")
_BY_SYMBOL_KEYS = ("max_position_pct_by_symbol", "stop_loss_by_symbol")

_KNOWN_KEYS = frozenset({*_NUMERIC_KEYS, *_INT_KEYS, *_BY_SYMBOL_KEYS})


def _finite_non_negative(value: float, key: str) -> float:
    value = float(value)
    if not (value == value) or value in (math.inf, -math.inf) or value < 0:
        raise ValueError(f"risk_limits.{key} 必须是非负有限数,得到 {value!r}")
    return value


def parse_risk_limits(block: dict) -> RiskLimits:
    """Validate a ``risk_limits`` block into a :class:`RiskLimits`."""
    if not isinstance(block, dict):
        raise ValueError("risk_limits 必须是对象")
    unknown = set(block) - _KNOWN_KEYS
    if unknown:
        raise ValueError(f"risk_limits 存在未知键: {sorted(unknown)}")

    numeric: dict[str, float] = {}
    for key in _NUMERIC_KEYS:
        value = block.get(key)
        if value is not None:
            numeric[key] = _finite_non_negative(value, key)
    ints: dict[str, int] = {}
    for key in _INT_KEYS:
        value = block.get(key)
        if value is not None:
            try:
                ivalue = int(value)
            except (TypeError, ValueError):
                raise ValueError(f"risk_limits.{key} 必须是整数,得到 {value!r}") from None
            if ivalue < 0 or ivalue != value:
                raise ValueError(f"risk_limits.{key} 必须是非负整数,得到 {value!r}")
            ints[key] = ivalue
    by_symbol: dict[str, dict[str, float]] = {}
    for key in _BY_SYMBOL_KEYS:
        raw = block.get(key)
        if raw is None:
            continue
        if not isinstance(raw, dict):
            raise ValueError(f"risk_limits.{key} 必须是 symbol->数值 对象")
        parsed: dict[str, float] = {}
        for symbol, value in raw.items():
            if not isinstance(symbol, str) or not symbol.strip():
                raise ValueError(f"risk_limits.{key} 键必须是非空 symbol")
            parsed[symbol.strip()] = _finite_non_negative(value, f"{key}.{symbol}")
        by_symbol[key] = parsed

    return RiskLimits(
        max_position_pct=numeric.get("max_position_pct"),
        max_position_pct_by_symbol=by_symbol.get("max_position_pct_by_symbol", {}),
        max_gross_leverage=numeric.get("max_gross_leverage"),
        max_net_leverage=numeric.get("max_net_leverage"),
        max_concentration_pct=numeric.get("max_concentration_pct"),
        stop_loss=numeric.get("stop_loss"),
        stop_loss_by_symbol=by_symbol.get("stop_loss_by_symbol", {}),
        portfolio_drawdown_halt=numeric.get("portfolio_drawdown_halt"),
        circuit_breaker_bars=ints.get("circuit_breaker_bars"),
        max_orders_per_bar=ints.get("max_orders_per_bar"),
    )
