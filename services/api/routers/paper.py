"""Paper-only execution HTTP adapter (E6-1)."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.models import (
    PaperAccount,
    PaperOrder,
    PaperPosition,
    PaperReconciliation,
    Strategy,
)
from services.api.schemas import (
    PaperAccountOut,
    PaperOrderAccepted,
    PaperOrderIn,
    PaperOrderOut,
    PaperPositionOut,
    PaperPositionsOut,
    PaperReconciliationOut,
)

router = APIRouter(prefix="/paper", tags=["paper"])


@router.post("/orders", response_model=PaperOrderAccepted, status_code=status.HTTP_202_ACCEPTED)
def create_paper_order(payload: PaperOrderIn, db: Session = Depends(get_db)) -> PaperOrderAccepted:
    if db.get(Strategy, payload.strategy_id) is None:
        raise HTTPException(status_code=404, detail="策略不存在")
    from services.worker.tasks import run_paper_order_task

    run_paper_order_task.delay(payload.model_dump(mode="json"))
    return PaperOrderAccepted(status="queued")


@router.get("/orders", response_model=list[PaperOrderOut])
def list_paper_orders(
    strategy_id: UUID = Query(...),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[PaperOrderOut]:
    rows = db.scalars(
        select(PaperOrder)
        .where(PaperOrder.strategy_id == strategy_id)
        .order_by(PaperOrder.created_at.desc())
        .limit(limit)
    ).all()
    return [PaperOrderOut.model_validate(row) for row in rows]


@router.get("/positions", response_model=PaperPositionsOut)
def get_paper_positions(
    strategy_id: UUID = Query(...), db: Session = Depends(get_db)
) -> PaperPositionsOut:
    account = db.scalar(select(PaperAccount).where(PaperAccount.strategy_id == strategy_id))
    positions = db.scalars(
        select(PaperPosition)
        .where(PaperPosition.strategy_id == strategy_id)
        .order_by(PaperPosition.symbol)
    ).all()
    return PaperPositionsOut(
        account=PaperAccountOut.model_validate(account) if account else None,
        positions=[PaperPositionOut.model_validate(row) for row in positions],
    )


@router.get("/reconciliation", response_model=Optional[PaperReconciliationOut])
def get_paper_reconciliation(
    strategy_id: UUID = Query(...), db: Session = Depends(get_db)
) -> Optional[PaperReconciliationOut]:
    row = db.scalar(
        select(PaperReconciliation)
        .where(PaperReconciliation.strategy_id == strategy_id)
        .order_by(PaperReconciliation.created_at.desc())
    )
    return PaperReconciliationOut.model_validate(row) if row else None
