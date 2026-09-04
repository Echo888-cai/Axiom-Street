from __future__ import annotations

import asyncio
import json
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from services.api.db import SessionLocal, get_db
from services.api.models import BacktestStatus
from services.api.schemas import (
    BacktestCreate,
    BacktestLogsOut,
    BacktestMetricsOut,
    BacktestOut,
    BacktestPage,
    EquityPage,
    EquityPoint,
    MonthlyReturnOut,
    RollingWindowOut,
    TimeSeriesPointOut,
    TradeOut,
    TradePage,
)
from services.api.services import backtests as backtest_service

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.get("", response_model=BacktestPage)
def list_backtests(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    strategy_id: UUID | None = None,
    status: BacktestStatus | None = None,
    start_from: date | None = None,
    end_to: date | None = None,
) -> BacktestPage:
    rows, total = backtest_service.list_backtests(
        db,
        limit=limit,
        offset=offset,
        strategy_id=strategy_id,
        status_filter=status,
        start_from=start_from,
        end_to=end_to,
    )
    return BacktestPage(
        items=[backtest_service.to_out(db, b) for b in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


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


@router.get("/{backtest_id}/equity", response_model=EquityPage)
def get_equity(
    backtest_id: UUID,
    db: Session = Depends(get_db),
    limit: int = Query(5000, ge=1, le=50_000),
    offset: int = Query(0, ge=0),
) -> EquityPage:
    rows, total = backtest_service.get_equity(db, backtest_id, limit=limit, offset=offset)
    return EquityPage(
        items=[
            EquityPoint(
                ts=p.ts,
                strategy_value=p.strategy_value,
                benchmark_value=p.benchmark_value,
                drawdown=p.drawdown,
            )
            for p in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{backtest_id}/drawdowns")
def get_drawdowns(backtest_id: UUID, db: Session = Depends(get_db)) -> list[dict]:
    return backtest_service.get_drawdowns(db, backtest_id)


@router.get("/{backtest_id}/trades", response_model=TradePage)
def get_trades(
    backtest_id: UUID,
    db: Session = Depends(get_db),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> TradePage:
    rows, total = backtest_service.get_trades(db, backtest_id, limit=limit, offset=offset)
    return TradePage(
        items=[TradeOut.model_validate(t) for t in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{backtest_id}/monthly-returns", response_model=list[MonthlyReturnOut])
def get_monthly_returns(backtest_id: UUID, db: Session = Depends(get_db)) -> list[MonthlyReturnOut]:
    return [
        MonthlyReturnOut(year=r.year, month=r.month, return_pct=r.return_pct)
        for r in backtest_service.get_monthly_returns(db, backtest_id)
    ]


@router.get("/{backtest_id}/rolling-windows", response_model=list[RollingWindowOut])
def get_rolling_windows(backtest_id: UUID, db: Session = Depends(get_db)) -> list[RollingWindowOut]:
    return [
        RollingWindowOut(
            window_key=row.window_key,
            period_end=row.period_end,
            sharpe=row.sharpe,
            var_95=row.var_95,
            var_99=row.var_99,
            probabilistic_sharpe=row.probabilistic_sharpe,
            extras=row.extras or {},
        )
        for row in backtest_service.get_rolling_windows(db, backtest_id)
    ]


@router.get("/{backtest_id}/time-series", response_model=list[TimeSeriesPointOut])
def get_time_series(
    backtest_id: UUID,
    name: str | None = None,
    db: Session = Depends(get_db),
) -> list[TimeSeriesPointOut]:
    return [
        TimeSeriesPointOut(name=row.name, ts=row.ts, value=row.value)
        for row in backtest_service.get_time_series(db, backtest_id, name=name)
    ]


@router.get("/{backtest_id}/logs", response_model=BacktestLogsOut)
def get_logs(backtest_id: UUID, db: Session = Depends(get_db)) -> BacktestLogsOut:
    backtest_service.get_backtest(db, backtest_id)
    return BacktestLogsOut.model_validate(backtest_service.get_logs(backtest_id))


@router.get("/{backtest_id}/tearsheet.html")
def tearsheet_html(backtest_id: UUID, db: Session = Depends(get_db)) -> HTMLResponse:
    from services.api.services.tearsheet_export import render_html

    try:
        return HTMLResponse(render_html(db, backtest_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{backtest_id}/tearsheet.pdf")
def tearsheet_pdf(backtest_id: UUID, db: Session = Depends(get_db)) -> Response:
    from services.api.services.tearsheet_export import render_pdf

    try:
        payload = render_pdf(db, backtest_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="tearsheet-{backtest_id}.pdf"'},
    )


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
