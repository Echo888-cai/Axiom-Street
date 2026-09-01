import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from services.api.db import SessionLocal, get_db
from services.api.schemas import (
    BacktestCreate,
    BacktestMetricsOut,
    BacktestOut,
    EquityPoint,
    MonthlyReturnOut,
    TradeOut,
)
from services.api.services import backtests as backtest_service

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.get("", response_model=list[BacktestOut])
def list_backtests(db: Session = Depends(get_db)) -> list[BacktestOut]:
    return [backtest_service.to_out(db, b) for b in backtest_service.list_backtests(db)]


@router.post("", response_model=BacktestOut, status_code=201)
def create_backtest(payload: BacktestCreate, db: Session = Depends(get_db)) -> BacktestOut:
    return backtest_service.to_out(db, backtest_service.create_backtest(db, payload))


@router.get("/{backtest_id}", response_model=BacktestOut)
def get_backtest(backtest_id: UUID, db: Session = Depends(get_db)) -> BacktestOut:
    return backtest_service.to_out(db, backtest_service.get_backtest(db, backtest_id))


@router.post("/{backtest_id}/cancel", response_model=BacktestOut)
def cancel_backtest(backtest_id: UUID, db: Session = Depends(get_db)) -> BacktestOut:
    return backtest_service.to_out(db, backtest_service.cancel_backtest(db, backtest_id))


@router.get("/{backtest_id}/metrics", response_model=BacktestMetricsOut)
def get_metrics(backtest_id: UUID, db: Session = Depends(get_db)) -> BacktestMetricsOut:
    return BacktestMetricsOut.model_validate(backtest_service.get_metrics(db, backtest_id))


@router.get("/{backtest_id}/equity", response_model=list[EquityPoint])
def get_equity(backtest_id: UUID, db: Session = Depends(get_db)) -> list[EquityPoint]:
    return [
        EquityPoint(
            ts=p.ts,
            strategy_value=p.strategy_value,
            benchmark_value=p.benchmark_value,
            drawdown=p.drawdown,
        )
        for p in backtest_service.get_equity(db, backtest_id)
    ]


@router.get("/{backtest_id}/drawdowns")
def get_drawdowns(backtest_id: UUID, db: Session = Depends(get_db)) -> list[dict]:
    return backtest_service.get_drawdowns(db, backtest_id)


@router.get("/{backtest_id}/trades", response_model=list[TradeOut])
def get_trades(backtest_id: UUID, db: Session = Depends(get_db)) -> list[TradeOut]:
    return [TradeOut.model_validate(t) for t in backtest_service.get_trades(db, backtest_id)]


@router.get("/{backtest_id}/monthly-returns", response_model=list[MonthlyReturnOut])
def get_monthly_returns(backtest_id: UUID, db: Session = Depends(get_db)) -> list[MonthlyReturnOut]:
    return [
        MonthlyReturnOut(year=r.year, month=r.month, return_pct=r.return_pct)
        for r in backtest_service.get_monthly_returns(db, backtest_id)
    ]


@router.get("/{backtest_id}/events")
async def backtest_events(backtest_id: UUID) -> EventSourceResponse:
    async def event_generator():
        terminal = {"COMPLETED", "FAILED", "CANCELLED"}
        while True:
            db = SessionLocal()
            try:
                backtest = backtest_service.get_backtest(db, backtest_id)
                payload = {
                    "backtest_id": str(backtest.id),
                    "status": backtest.status.value,
                    "progress_step": backtest.progress_step,
                    "error": backtest.error,
                }
                yield {
                    "event": "progress",
                    "data": json.dumps(payload),
                }
                if backtest.status.value in terminal:
                    yield {"event": "done", "data": json.dumps(payload)}
                    break
            finally:
                db.close()
            await asyncio.sleep(1.0)

    return EventSourceResponse(event_generator())
