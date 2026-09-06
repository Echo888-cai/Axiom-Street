"""Backtest-domain Celery work: execution, cancellation-aware progress, and
orphan reconciliation. Task name registrations here keep their historical
Celery names (``backtests.run``, ``backtests.reconcile_orphans``).

Runtime dependencies (``SessionLocal``, ``LeanQuantEngine``) are read through
the package namespace so unit tests that patch ``services.worker.tasks.<name>``
keep working after the split.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import structlog

from quant.engine.base import BacktestRequest
from quant.engine.errors import BacktestCancelled, EngineTimeout, strategy_error_location
from quant.strategy_sdk.spy_200dma import DEFAULT_STRATEGY_CLASS
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
    ValidationKind,
    ValidationRun,
    ValidationRunStatus,
)
from services.api.settings import get_settings
from services.worker import tasks as _tasks
from services.worker.celery_app import celery_app

from ._common import (
    _set_progress,
    _validation_step_count,
    is_cancel_flagged,
    log,
    resolve_execution_universe,
)


def reconcile_orphan_backtests(*, worker_restart: bool = False) -> int:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=settings.lean_timeout_seconds)
    db = _tasks.SessionLocal()
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
        wf_rows = (
            db.query(ValidationRun)
            .filter(
                ValidationRun.kind.in_(
                    [
                        ValidationKind.WALK_FORWARD,
                        ValidationKind.PBO,
                        ValidationKind.SENSITIVITY,
                        ValidationKind.COST,
                        ValidationKind.BOOTSTRAP,
                    ]
                ),
                ValidationRun.status.in_([ValidationRunStatus.QUEUED, ValidationRunStatus.RUNNING]),
            )
            .all()
        )
        for run in wf_rows:
            created = run.created_at or now
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            n_steps = _validation_step_count(run.params)
            wf_cutoff = now - timedelta(seconds=settings.lean_timeout_seconds * n_steps + 120)
            died_on_restart = worker_restart and run.status == ValidationRunStatus.RUNNING
            stale = created < wf_cutoff
            if not (died_on_restart or stale):
                continue
            run.status = ValidationRunStatus.FAILED
            run.finished_at = now
            run.progress_step = "Failed"
            run.error = {
                "code": "orphaned_by_restart",
                "message": "验证任务在 worker 重启或超时后成为孤儿任务",
            }
            count += 1
        db.commit()
    finally:
        db.close()
    return count


def execute_backtest(backtest_id: str, *, record_gates: bool = True) -> dict:
    settings = get_settings()
    structlog.contextvars.bind_contextvars(backtest_id=backtest_id)
    db = _tasks.SessionLocal()
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
        snap = None
        if backtest.data_snapshot_id:
            snap = db.get(DataSnapshot, backtest.data_snapshot_id)
            if snap:
                candidate = Path(settings.data_root) / "snapshots" / snap.snapshot_key
                if candidate.exists():
                    data_root = candidate
        try:
            universe, memberships = resolve_execution_universe(
                universe_snapshot=backtest.universe_snapshot,
                snapshot_symbols=snap.symbols if snap else None,
                config=version.config,
            )
        except ValueError as exc:
            backtest.status = BacktestStatus.FAILED
            backtest.error = {"code": "universe_missing", "message": str(exc)}
            backtest.finished_at = datetime.now(timezone.utc)
            backtest.progress_step = "Failed"
            db.commit()
            return {"error": "universe_missing", "message": str(exc)}

        engine = _tasks.LeanQuantEngine(
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
            memberships=memberships,
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
            line = strategy_error_location(str(exc))
            if line is not None:
                backtest.error["line"] = line
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
        from services.api.services.backtest_cache import result_fingerprint

        backtest.result_fingerprint = result_fingerprint(
            code=version.code,
            data_snapshot_id=backtest.data_snapshot_id,
            engine_version=result.engine_version,
            start_date=backtest.start_date,
            end_date=backtest.end_date,
            benchmark=backtest.benchmark,
            initial_capital=backtest.initial_capital,
            universe=universe,
            universe_id=backtest.universe_id,
            parameters=backtest.parameters or {},
        )
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

        db.flush()
        from services.api.services.validation import (
            maybe_apply_validated,
            record_bootstrap_for_backtest,
            record_dsr_for_backtest,
            record_regime_for_backtest,
        )

        if record_gates:
            record_dsr_for_backtest(
                db,
                backtest,
                metrics,
                n_obs=max(len(result.equity) - 1, 0),
            )
            record_bootstrap_for_backtest(db, backtest, result.equity)
            record_regime_for_backtest(db, backtest, result.equity)
            maybe_apply_validated(
                db,
                strategy_id=version.strategy_id,
                strategy_version_id=version.id,
            )

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
