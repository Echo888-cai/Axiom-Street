"""Pure fail-closed Live readiness policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

REQUIRED_VALIDATION_KINDS = (
    "WALK_FORWARD",
    "DSR",
    "PBO",
    "SENSITIVITY",
    "COST",
    "BOOTSTRAP",
    "REGIME",
    "SPA",
)


@dataclass(frozen=True)
class LiveReadiness:
    ready: bool
    reasons: list[str]
    evidence: dict[str, object]


def evaluate_live_readiness(
    *,
    strategy_status: str,
    validation_passed: Mapping[str, bool],
    risk_config_valid: bool,
    paper_reconciliation_status: str | None,
    live_enabled: bool,
    broker_implemented: bool,
) -> LiveReadiness:
    normalized_status = str(strategy_status).upper()
    normalized_reconciliation = (
        str(paper_reconciliation_status).upper() if paper_reconciliation_status else None
    )
    missing_validation = [
        kind for kind in REQUIRED_VALIDATION_KINDS if not bool(validation_passed.get(kind, False))
    ]
    reasons: list[str] = []
    if normalized_status != "APPROVED":
        reasons.append("strategy_not_approved")
    if missing_validation:
        reasons.append("validation_incomplete")
    if not risk_config_valid:
        reasons.append("risk_limits_invalid")
    if normalized_reconciliation != "MATCHED":
        reasons.append("paper_reconciliation_not_matched")
    if not live_enabled:
        reasons.append("live_disabled")
    if not broker_implemented:
        reasons.append("live_broker_unavailable")
    return LiveReadiness(
        ready=not reasons,
        reasons=reasons,
        evidence={
            "strategy_status": normalized_status,
            "validation_kinds": list(REQUIRED_VALIDATION_KINDS),
            "missing_validation": missing_validation,
            "risk_config_valid": risk_config_valid,
            "paper_reconciliation_status": normalized_reconciliation,
            "live_enabled": live_enabled,
            "broker_implemented": broker_implemented,
        },
    )
