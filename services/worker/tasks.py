from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from quant.engine.base import BacktestRequest
from quant.engine.lean import LeanQuantEngine
from quant.strategy_sdk.spy_200dma import DEFAULT_STRATEGY_CLASS
from services.api.db import SessionLocal
from services.api.models import (
    Backtest,
    BacktestEquity,
    BacktestMetrics,
    BacktestMonthlyReturn,
    BacktestStatus,
    BacktestTrade,
    Strategy,
    StrategyStatus,
    StrategyVersion,
)
from services.api.settings import get_settings
from services.worker.celery_app import celery_app


def _set_progress(db, backtest: Backtest, status: BacktestStatus, step: str) -> None:
    backtest.status = status
    backtest.progress_step = step
    db.commit()


def execute_backtest(backtest_id: str) -> dict:
    settings = get_settings()
    db = SessionLocal()
    try:
        backtest = db.get(Backtest, UUID(backtest_id))
        if not backtest:
            return {"error": "not_found"}
        if backtest.status == BacktestStatus.CANCELLED:
            return {"status": "CANCELLED"}

        version = db.get(StrategyVersion, backtest.strategy_version_id)
        if not version:
            backtest.status = BacktestStatus.FAILED
            backtest.error = {"message": "策略版本不存在"}
            db.commit()
            return {"error": "version_missing"}

        backtest.started_at = datetime.now(timezone.utc)
        _set_progress(db, backtest, BacktestStatus.STARTING, "Preparing environment")

        engine = LeanQuantEngine(
            lean_image=settings.lean_image,
            data_root=Path(settings.data_root),
            jobs_root=Path(settings.jobs_root),
        )
        engine.risk_free_rate = settings.risk_free_rate

        def on_progress(step: str) -> None:
            db.refresh(backtest)
            if backtest.status == BacktestStatus.CANCELLED:
                engine.cancel_backtest(backtest_id)
                return
            _set_progress(db, backtest, BacktestStatus.RUNNING, step)

        request = BacktestRequest(
            backtest_id=backtest_id,
            strategy_code=version.code,
            strategy_class_name=version.config.get("class_name", DEFAULT_STRATEGY_CLASS)
            if isinstance(version.config, dict)
            else DEFAULT_STRATEGY_CLASS,
            start_date=backtest.start_date,
            end_date=backtest.end_date,
            benchmark=backtest.benchmark,
            initial_capital=backtest.initial_capital,
            parameters=backtest.parameters or {},
        )

        try:
            result = engine.run_backtest(request, on_progress=on_progress)
        except Exception as exc:  # noqa: BLE001 - persist failure for UI
            backtest.status = BacktestStatus.FAILED
            backtest.error = {"message": str(exc)}
            backtest.finished_at = datetime.now(timezone.utc)
            backtest.progress_step = "Failed"
            db.commit()
            return {"status": "FAILED", "error": str(exc)}

        db.refresh(backtest)
        if backtest.status == BacktestStatus.CANCELLED:
            return {"status": "CANCELLED"}

        # Clear previous result rows if re-run
        db.query(BacktestEquity).filter(BacktestEquity.backtest_id == backtest.id).delete()
        db.query(BacktestTrade).filter(BacktestTrade.backtest_id == backtest.id).delete()
        db.query(BacktestMonthlyReturn).filter(
            BacktestMonthlyReturn.backtest_id == backtest.id
        ).delete()
        existing_metrics = db.get(BacktestMetrics, backtest.id)
        if existing_metrics:
            db.delete(existing_metrics)
        db.flush()

        metrics = result.statistics
        metric_fields = {
            c.name
            for c in BacktestMetrics.__table__.columns
            if c.name not in {"backtest_id", "extras"}
        }
        db.add(
            BacktestMetrics(
                backtest_id=backtest.id,
                extras=metrics.get("extras") or {},
                **{k: metrics.get(k) for k in metric_fields},
            )
        )

        for point in result.equity:
            db.add(
                BacktestEquity(
                    backtest_id=backtest.id,
                    ts=point["ts"],
                    strategy_value=point["strategy_value"],
                    benchmark_value=point.get("benchmark_value"),
                    drawdown=point.get("drawdown"),
                )
            )

        for trade in result.trades:
            db.add(
                BacktestTrade(
                    backtest_id=backtest.id,
                    trade_date=trade["trade_date"],
                    ticker=trade["ticker"],
                    direction=str(trade["direction"]),
                    quantity=float(trade["quantity"]),
                    entry_price=trade.get("entry_price"),
                    exit_price=trade.get("exit_price"),
                    pnl=trade.get("pnl"),
                    return_pct=trade.get("return_pct"),
                    holding_period=trade.get("holding_period"),
                    commission=trade.get("commission"),
                    slippage=trade.get("slippage"),
                    signal=trade.get("signal"),
                    raw=trade.get("raw") or {},
                )
            )

        for row in result.monthly_returns:
            db.add(
                BacktestMonthlyReturn(
                    backtest_id=backtest.id,
                    year=int(row["year"]),
                    month=int(row["month"]),
                    return_pct=float(row["return_pct"]),
                )
            )

        backtest.engine_version = result.engine_version
        backtest.data_version = result.data_version
        backtest.status = BacktestStatus.COMPLETED
        backtest.progress_step = "Completed"
        backtest.finished_at = datetime.now(timezone.utc)
        backtest.error = None

        strategy = db.get(Strategy, version.strategy_id)
        if strategy and strategy.status == StrategyStatus.DRAFT:
            strategy.status = StrategyStatus.BACKTESTED

        db.commit()
        return {"status": "COMPLETED", "backtest_id": backtest_id}
    finally:
        db.close()


@celery_app.task(name="backtests.run")
def run_backtest_task(backtest_id: str) -> dict:
    return execute_backtest(backtest_id)
