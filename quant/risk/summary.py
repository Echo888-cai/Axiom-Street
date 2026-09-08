"""Pure paper-account risk summary calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from quant.risk.limits import parse_risk_limits

PAPER_READY_STATUSES = frozenset({"VALIDATED", "PAPER", "APPROVED"})


@dataclass(frozen=True)
class RiskPosition:
    quantity: float
    mark_price: float


@dataclass(frozen=True)
class RiskSummary:
    strategy_status: str
    risk_limits: dict[str, object] | None
    risk_config_valid: bool
    account_available: bool
    initial_capital: float | None
    cash: float | None
    equity: float | None
    gross_exposure: float | None
    net_exposure: float | None
    reconciliation_status: str | None
    blocking_reasons: tuple[str, ...]


def _finite(value: float, name: str) -> float:
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def summarize_risk(
    *,
    strategy_status: str,
    risk_config: Mapping[str, object] | None,
    initial_capital: float | None,
    cash: float | None,
    positions: Sequence[RiskPosition],
    reconciliation_status: str | None,
) -> RiskSummary:
    """Build a fail-closed, read-only risk summary from paper state."""

    normalized_status = str(strategy_status).upper()
    risk_limits = dict(risk_config) if isinstance(risk_config, Mapping) else None
    risk_config_valid = False
    if risk_limits is not None:
        try:
            parse_risk_limits(risk_limits)
        except ValueError:
            risk_config_valid = False
        else:
            risk_config_valid = True

    account_available = initial_capital is not None and cash is not None
    equity: float | None = None
    gross_exposure: float | None = None
    net_exposure: float | None = None
    if account_available:
        assert initial_capital is not None and cash is not None
        capital = _finite(initial_capital, "initial_capital")
        cash_value = _finite(cash, "cash")
        equity = cash_value
        gross_value = 0.0
        net_value = 0.0
        for position in positions:
            quantity = _finite(position.quantity, "position.quantity")
            mark_price = _finite(position.mark_price, "position.mark_price")
            market_value = quantity * mark_price
            equity += market_value
            gross_value += abs(market_value)
            net_value += market_value
        if equity <= 0:
            raise ValueError("paper account equity must remain positive")
        gross_exposure = gross_value / equity
        net_exposure = net_value / equity
        # Keep this conversion explicit so a non-finite initial capital cannot
        # silently enter the API response even though it is not in the ratio.
        _finite(capital, "initial_capital")

    reasons: list[str] = []
    if normalized_status not in PAPER_READY_STATUSES:
        reasons.append("strategy_not_paper_ready")
    if not risk_config_valid:
        reasons.append("risk_limits_invalid")
    if not account_available:
        reasons.append("paper_account_missing")
    if str(reconciliation_status).upper() != "MATCHED":
        reasons.append("paper_reconciliation_not_matched")

    return RiskSummary(
        strategy_status=normalized_status,
        risk_limits=risk_limits,
        risk_config_valid=risk_config_valid,
        account_available=account_available,
        initial_capital=(float(initial_capital) if initial_capital is not None else None),
        cash=float(cash) if cash is not None else None,
        equity=equity,
        gross_exposure=gross_exposure,
        net_exposure=net_exposure,
        reconciliation_status=reconciliation_status,
        blocking_reasons=tuple(reasons),
    )
