"""Fail-closed Live readiness and activation guard (E6-2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from quant.execution.readiness import evaluate_live_readiness
from quant.risk.limits import parse_risk_limits
from services.api.db import get_db
from services.api.models import (
    PaperReconciliation,
    Strategy,
    StrategyVersion,
    ValidationKind,
    ValidationRun,
    ValidationRunStatus,
)
from services.api.schemas import LiveActivateIn, LiveReadinessOut
from services.api.settings import get_settings

router = APIRouter(prefix="/live", tags=["live"])
LIVE_BROKER_IMPLEMENTED = False


def _readiness(db: Session, strategy_id: UUID) -> LiveReadinessOut:
    strategy = db.get(Strategy, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="策略不存在")
    version = db.scalars(
        select(StrategyVersion)
        .where(StrategyVersion.strategy_id == strategy_id)
        .order_by(StrategyVersion.version.desc())
        .limit(1)
    ).first()
    validation_passed = {kind.value: False for kind in ValidationKind}
    if version is not None:
        rows = db.scalars(
            select(ValidationRun)
            .where(
                ValidationRun.strategy_id == strategy_id,
                ValidationRun.strategy_version_id == version.id,
                ValidationRun.status == ValidationRunStatus.COMPLETED,
            )
            .order_by(ValidationRun.created_at.desc())
        ).all()
        for row in rows:
            key = row.kind.value
            if not validation_passed[key]:
                validation_passed[key] = bool(row.passed and row.error is None)

    risk_config_valid = False
    if version is not None and isinstance(version.config, dict) and "risk_limits" in version.config:
        try:
            parse_risk_limits(version.config["risk_limits"])
            risk_config_valid = True
        except ValueError:
            risk_config_valid = False

    reconciliation = db.scalars(
        select(PaperReconciliation)
        .where(PaperReconciliation.strategy_id == strategy_id)
        .order_by(PaperReconciliation.created_at.desc())
        .limit(1)
    ).first()
    reconciliation_status = reconciliation.status.value if reconciliation else None
    result = evaluate_live_readiness(
        strategy_status=strategy.status.value,
        validation_passed=validation_passed,
        risk_config_valid=risk_config_valid,
        paper_reconciliation_status=reconciliation_status,
        live_enabled=get_settings().live_enabled,
        broker_implemented=LIVE_BROKER_IMPLEMENTED,
    )
    return LiveReadinessOut(
        ready=result.ready,
        reasons=result.reasons,
        evidence={
            **result.evidence,
            "strategy_id": str(strategy_id),
            "version": version.version if version else None,
        },
    )


@router.get("/readiness", response_model=LiveReadinessOut)
def get_live_readiness(
    strategy_id: UUID = Query(...), db: Session = Depends(get_db)
) -> LiveReadinessOut:
    return _readiness(db, strategy_id)


@router.post("/activate", status_code=status.HTTP_204_NO_CONTENT)
def activate_live(payload: LiveActivateIn, db: Session = Depends(get_db)) -> None:
    readiness = _readiness(db, payload.strategy_id)
    if not readiness.ready:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "live_not_ready",
                "message": "Live 执行保持关闭,当前没有任何外部 Broker 会被调用",
                "reasons": readiness.reasons,
                "evidence": readiness.evidence,
            },
        )
    # This branch is intentionally unreachable while LIVE_BROKER_IMPLEMENTED is false.
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "live_broker_unavailable", "message": "Live Broker 尚未实现"},
    )
