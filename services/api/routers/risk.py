"""Read-only paper risk summary HTTP adapter."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from quant.risk.summary import RiskPosition, summarize_risk
from services.api.db import get_db
from services.api.models import (
    PaperAccount,
    PaperPosition,
    PaperReconciliation,
    Strategy,
    StrategyVersion,
)
from services.api.schemas import RiskSummaryOut

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/summary", response_model=RiskSummaryOut)
def get_risk_summary(
    strategy_id: UUID = Query(...), db: Session = Depends(get_db)
) -> RiskSummaryOut:
    strategy = db.get(Strategy, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="策略不存在")

    version = db.scalars(
        select(StrategyVersion)
        .where(StrategyVersion.strategy_id == strategy_id)
        .order_by(StrategyVersion.version.desc())
        .limit(1)
    ).first()
    risk_config = None
    if version is not None and isinstance(version.config, dict):
        raw_limits = version.config.get("risk_limits")
        if isinstance(raw_limits, dict):
            risk_config = raw_limits

    account = db.scalar(select(PaperAccount).where(PaperAccount.strategy_id == strategy_id))
    position_rows = db.scalars(
        select(PaperPosition).where(PaperPosition.strategy_id == strategy_id)
    ).all()
    reconciliation = db.scalars(
        select(PaperReconciliation)
        .where(PaperReconciliation.strategy_id == strategy_id)
        .order_by(PaperReconciliation.created_at.desc())
        .limit(1)
    ).first()

    try:
        summary = summarize_risk(
            strategy_status=strategy.status.value,
            risk_config=risk_config,
            initial_capital=account.initial_capital if account else None,
            cash=account.cash if account else None,
            positions=[
                RiskPosition(quantity=row.quantity, mark_price=row.mark_price)
                for row in position_rows
            ],
            reconciliation_status=reconciliation.status.value if reconciliation else None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "risk_state_invalid", "message": str(exc)},
        ) from exc

    return RiskSummaryOut(
        strategy_id=strategy_id,
        strategy_status=summary.strategy_status,
        risk_limits=summary.risk_limits,
        risk_config_valid=summary.risk_config_valid,
        account_available=summary.account_available,
        initial_capital=summary.initial_capital,
        cash=summary.cash,
        equity=summary.equity,
        gross_exposure=summary.gross_exposure,
        net_exposure=summary.net_exposure,
        reconciliation_status=summary.reconciliation_status,
        blocking_reasons=list(summary.blocking_reasons),
    )
