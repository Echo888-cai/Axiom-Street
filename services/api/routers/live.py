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
    evidence_reasons = {}
    evidence_backtest_id = None
    if version is not None:
        from services.api.services.validation_evidence import collect_validation_evidence

        evidence = collect_validation_evidence(
            db, strategy_id=strategy_id, strategy_version_id=version.id
        )
        validation_passed = {kind.value: passed for kind, passed in evidence.passed.items()}
        evidence_reasons = evidence.reasons
        evidence_backtest_id = evidence.backtest_id

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
            "validation_reasons": evidence_reasons,
            "validation_backtest_id": str(evidence_backtest_id) if evidence_backtest_id else None,
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
    """P6B/C 实盘激活守卫：授权令牌 → 资金上限 → readiness（券商/证据），
    全部在网络调用之前判定；未授权一律拒绝，绝不冒充通过。"""
    settings = get_settings()
    expected = settings.live_authorization_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "live_authorization_not_configured",
                "message": "实盘未授权：服务端未配置授权令牌（STREET_LIVE_AUTHORIZATION_TOKEN）。真实资金需要单独取得明确授权。",
            },
        )
    if payload.authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "live_authorization_invalid",
                "message": "授权令牌不正确，拒绝激活实盘。",
            },
        )
    if settings.live_capital_cap <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "live_capital_cap_missing",
                "message": "未配置资金上限（STREET_LIVE_CAPITAL_CAP），拒绝激活实盘。",
            },
        )
    if payload.capital_cap is None or payload.capital_cap > settings.live_capital_cap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "live_capital_cap_exceeded",
                "message": f"资金上限超过服务端配置（≤ {settings.live_capital_cap}）。",
            },
        )

    readiness = _readiness(db, payload.strategy_id)
    if not readiness.ready:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "live_not_ready",
                "message": "Live 执行保持关闭：证据/券商/隔离条件未满足，当前没有任何外部 Broker 会被调用。",
                "reasons": readiness.reasons,
                "evidence": readiness.evidence,
            },
        )
    # This branch is intentionally unreachable while LIVE_BROKER_IMPLEMENTED is false.
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "live_broker_unavailable", "message": "Live Broker 尚未实现"},
    )


@router.post("/emergency-stop")
def emergency_stop(db: Session = Depends(get_db)) -> dict:
    """P6C 独立紧急停止：与策略/会话状态解耦，幂等。"""
    from services.api.models import AuditLog

    db.add(
        AuditLog(
            actor="local",
            action="Live Emergency Stop",
            object_type="live",
            object_id="global",
        )
    )
    db.commit()
    return {
        "stopped": True,
        "note": "紧急停止是独立通道：不依赖策略状态；只阻断新增风险，不自动平仓。",
    }
