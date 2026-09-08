"""Fail-closed Live readiness policy tests (E6-2)."""

from __future__ import annotations

from quant.execution.readiness import REQUIRED_VALIDATION_KINDS, evaluate_live_readiness


def test_readiness_reports_every_blocking_reason() -> None:
    result = evaluate_live_readiness(
        strategy_status="VALIDATED",
        validation_passed={"DSR": True},
        risk_config_valid=False,
        paper_reconciliation_status="DRIFT",
        live_enabled=False,
        broker_implemented=False,
    )

    assert result.ready is False
    assert set(result.reasons) == {
        "strategy_not_approved",
        "validation_incomplete",
        "risk_limits_invalid",
        "paper_reconciliation_not_matched",
        "live_disabled",
        "live_broker_unavailable",
    }


def test_readiness_is_true_only_with_complete_evidence() -> None:
    result = evaluate_live_readiness(
        strategy_status="APPROVED",
        validation_passed={kind: True for kind in REQUIRED_VALIDATION_KINDS},
        risk_config_valid=True,
        paper_reconciliation_status="MATCHED",
        live_enabled=True,
        broker_implemented=True,
    )

    assert result.ready is True
    assert result.reasons == []
    assert result.evidence["validation_kinds"] == list(REQUIRED_VALIDATION_KINDS)
