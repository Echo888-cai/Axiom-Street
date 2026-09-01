from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import redis
import structlog

from quant.engine.base import BacktestRequest
from quant.engine.errors import BacktestCancelled, EngineTimeout
from quant.engine.lean import LeanQuantEngine
from quant.strategy_sdk.spy_200dma import DEFAULT_STRATEGY_CLASS
from services.api.db import SessionLocal
from services.api.models import (
    Backtest,
    BacktestEquity,
    BacktestMetrics,
    BacktestMonthlyReturn,
    BacktestRollingWindow,
    BacktestStatus,
    BacktestTimeSeries,
    BacktestTrade,
    DataSnapshot,
    ExperimentTrial,
    Strategy,
    StrategyStatus,
    StrategyVersion,
)
from services.api.settings import get_settings
from services.worker.celery_app import celery_app

log = structlog.get_logger("axiom.worker")


def _redis():
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def cancel_key(backtest_id: str) -> str:
    return f"axiom:cancel:{backtest_id}"


def flag_cancel(backtest_id: str) -> None:
    try:
        _redis().setex(cancel_key(backtest_id), 3600, "1")
    except redis.RedisError:
        pass


def is_cancel_flagged(backtest_id: str) -> bool:
    try:
        return bool(_redis().get(cancel_key(backtest_id)))
    except redis.RedisError:
        return False


def _set_progress(db, backtest: Backtest, status: BacktestStatus, step: str) -> None:
    backtest.status = status
    backtest.progress_step = step
    db.commit()


def reconcile_orphan_backtests(*, worker_restart: bool = False) -> int:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=settings.lean_timeout_seconds)
    db = SessionLocal()
    count = 0
    try:
        rows = (
            db.query(Backtest)
            .filter(
                Backtest.status.in_(
                    [BacktestStatus.QUEUED, BacktestStatus.STARTING, BacktestStatus.RUNNING]
                )
            )
            .all()
        )
        for backtest in rows:
            created = backtest.created_at or now
            started = backtest.started_at or created
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            timed_out = started < cutoff
            died_on_restart = worker_restart and backtest.status in {
                BacktestStatus.STARTING,
                BacktestStatus.RUNNING,
            }
            stale_queue = backtest.status == BacktestStatus.QUEUED and created < cutoff
            if not (timed_out or died_on_restart or stale_queue):
                continue
            backtest.status = BacktestStatus.FAILED
            backtest.finished_at = now
            backtest.progress_step = "Failed"
            backtest.error = {
                "code": "orphaned_by_restart",
                "message": "回测在 worker 重启或超时后成为孤儿任务",
            }
            count += 1
        db.commit()
    finally:
        db.close()
    return count


def execute_backtest(backtest_id: str) -> dict:
    settings = get_settings()
    structlog.contextvars.bind_contextvars(backtest_id=backtest_id)
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
            backtest.error = {"code": "version_missing", "message": "策略版本不存在"}
            db.commit()
            return {"error": "version_missing"}

        backtest.started_at = datetime.now(timezone.utc)
        _set_progress(db, backtest, BacktestStatus.STARTING, "Preparing environment")

        data_root = Path(settings.data_root)
        universe = ["SPY"]
        if backtest.data_snapshot_id:
            snap = db.get(DataSnapshot, backtest.data_snapshot_id)
            if snap:
                from quant.data.symbols import as_symbol_list

                universe = as_symbol_list(snap.symbols)
                candidate = Path(settings.data_root) / "snapshots" / snap.snapshot_key
                if candidate.exists():
                    data_root = candidate
        if isinstance(version.config, dict):
            configured = (version.config.get("universe") or {}).get("symbols")
            if configured:
                from quant.data.symbols import as_symbol_list as _as_list

                universe = _as_list(configured)

        engine = LeanQuantEngine(
            lean_image=settings.lean_image,
            data_root=data_root,
            jobs_root=Path(settings.jobs_root),
        )
        engine.risk_free_rate = settings.risk_free_rate

        def on_progress(step: str) -> None:
            db.refresh(backtest)
            if backtest.status == BacktestStatus.CANCELLED or is_cancel_flagged(backtest_id):
                engine.cancel_backtest(backtest_id)
                return
            _set_progress(db, backtest, BacktestStatus.RUNNING, step)

        def _cancelled() -> bool:
            row = db.get(Backtest, UUID(backtest_id))
            return is_cancel_flagged(backtest_id) or (
                row is not None and row.status == BacktestStatus.CANCELLED
            )

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
            universe=universe,
            data_root=data_root,
            timeout_seconds=settings.lean_timeout_seconds,
            cancel_check=_cancelled,
        )

        try:
            result = engine.run_backtest(request, on_progress=on_progress)
        except BacktestCancelled:
            backtest.status = BacktestStatus.CANCELLED
            backtest.finished_at = datetime.now(timezone.utc)
            backtest.progress_step = "Cancelled"
            db.commit()
            return {"status": "CANCELLED"}
        except EngineTimeout as exc:
            backtest.status = BacktestStatus.FAILED
            backtest.error = {"code": "engine_timeout", "message": str(exc)}
            backtest.finished_at = datetime.now(timezone.utc)
            backtest.progress_step = "Failed"
            db.commit()
            return {"status": "FAILED", "error": str(exc)}
        except Exception as exc:  # noqa: BLE001 - persist failure for UI
            backtest.status = BacktestStatus.FAILED
            backtest.error = {"code": "engine_error", "message": str(exc)}
            backtest.finished_at = datetime.now(timezone.utc)
            backtest.progress_step = "Failed"
            db.commit()
            return {"status": "FAILED", "error": str(exc)}

        db.refresh(backtest)
        if backtest.status == BacktestStatus.CANCELLED:
            return {"status": "CANCELLED"}

        db.query(BacktestEquity).filter(BacktestEquity.backtest_id == backtest.id).delete()
        db.query(BacktestTrade).filter(BacktestTrade.backtest_id == backtest.id).delete()
        db.query(BacktestMonthlyReturn).filter(
            BacktestMonthlyReturn.backtest_id == backtest.id
        ).delete()
        db.query(BacktestRollingWindow).filter(
            BacktestRollingWindow.backtest_id == backtest.id
        ).delete()
        db.query(BacktestTimeSeries).filter(BacktestTimeSeries.backtest_id == backtest.id).delete()
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

        for window in result.rolling_windows:
            db.add(
                BacktestRollingWindow(
                    backtest_id=backtest.id,
                    window_key=window["window_key"],
                    period_end=window.get("period_end"),
                    sharpe=window.get("sharpe"),
                    var_95=window.get("var_95"),
                    var_99=window.get("var_99"),
                    probabilistic_sharpe=window.get("probabilistic_sharpe"),
                    extras=window.get("extras") or {},
                )
            )

        for point in result.time_series:
            db.add(
                BacktestTimeSeries(
                    backtest_id=backtest.id,
                    name=point["name"],
                    ts=point["ts"],
                    value=float(point["value"]),
                )
            )

        backtest.engine_version = result.engine_version
        backtest.data_version = result.data_version
        backtest.status = BacktestStatus.COMPLETED
        backtest.progress_step = "Completed"
        backtest.finished_at = datetime.now(timezone.utc)
        backtest.error = None

        trial = db.query(ExperimentTrial).filter(ExperimentTrial.backtest_id == backtest.id).first()
        if trial:
            trial.observed_sharpe = metrics.get("sharpe")

        strategy = db.get(Strategy, version.strategy_id)
        if strategy and strategy.status == StrategyStatus.DRAFT:
            strategy.status = StrategyStatus.BACKTESTED

        db.commit()
        log.info("backtest_completed", engine_version=result.engine_version)
        return {"status": "COMPLETED", "backtest_id": backtest_id}
    finally:
        db.close()
        structlog.contextvars.unbind_contextvars("backtest_id")


@celery_app.task(name="backtests.run")
def run_backtest_task(backtest_id: str) -> dict:
    return execute_backtest(backtest_id)


@celery_app.task(name="backtests.reconcile_orphans")
def reconcile_orphan_backtests_task() -> int:
    return reconcile_orphan_backtests()


@celery_app.task(name="worker.publish_health")
def publish_health_task() -> dict:
    from services.worker.health import publish_worker_health

    return publish_worker_health()
