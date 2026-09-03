from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import redis
import structlog

from quant.data.symbols import as_symbol_list
from quant.data.universe import Membership
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
    ValidationKind,
    ValidationRun,
    ValidationRunStatus,
)
from services.api.settings import get_settings
from services.worker.celery_app import celery_app

log = structlog.get_logger("axiom.worker")

_NO_UNIVERSE = "回测没有标的。请指定标的池、临时 symbols，或先拉取行情。"


def resolve_execution_universe(
    *,
    universe_snapshot: list | None,
    snapshot_symbols: object | None,
    config: object | None,
) -> tuple[list[str], list[Membership]]:
    """PIT snapshot wins. Never guess SPY."""
    memberships: list[Membership] = []
    universe: list[str] = []
    if universe_snapshot:
        memberships = [Membership.from_dict(item) for item in universe_snapshot]
        for member in memberships:
            if member.symbol not in universe:
                universe.append(member.symbol)
        if universe:
            return universe, memberships
    if snapshot_symbols:
        universe = as_symbol_list(snapshot_symbols)
        return universe, memberships
    if isinstance(config, dict):
        configured = (config.get("universe") or {}).get("symbols")
        if configured:
            universe = as_symbol_list(configured)
            return universe, memberships
    raise ValueError(_NO_UNIVERSE)


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
                ValidationRun.status.in_(
                    [ValidationRunStatus.QUEUED, ValidationRunStatus.RUNNING]
                ),
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


def _validation_step_count(params: dict | None) -> int:
    payload = params or {}
    for key in ("folds", "values", "costs_bps"):
        items = payload.get(key) or []
        if isinstance(items, list) and items:
            return max(len(items), 1)
    return 1


def _fail_walk_forward(db, run: ValidationRun, code: str, message: str) -> dict:
    run.status = ValidationRunStatus.FAILED
    run.passed = False
    run.progress_step = "Failed"
    run.finished_at = datetime.now(timezone.utc)
    run.error = {"code": code, "message": message}
    db.commit()
    return {"status": "FAILED", "error": message}


class _ScanFailed(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _universe_key(members: object) -> str:
    if isinstance(members, list):
        symbols = [
            str(item.get("symbol", ""))
            for item in members
            if isinstance(item, dict) and item.get("symbol")
        ]
        if symbols:
            return ",".join(symbols)
    return "SPY"


def _run_scan_backtest(
    db,
    *,
    version: StrategyVersion,
    start: date,
    end: date,
    params: dict,
    bt_params: dict,
    snapshot_id: UUID | None,
    hash_extra: dict,
) -> tuple[Backtest, list[dict]]:
    from services.api.hashing import canonical_hash

    strategy = db.get(Strategy, version.strategy_id)
    backtest = Backtest(
        strategy_version_id=version.id,
        start_date=start,
        end_date=end,
        benchmark=str(params.get("benchmark") or "SPY"),
        initial_capital=float(params.get("initial_capital") or 100_000.0),
        parameters=dict(bt_params),
        status=BacktestStatus.QUEUED,
        progress_step="Queued",
        data_snapshot_id=snapshot_id,
        universe_snapshot=params.get("universe_snapshot") or [],
    )
    db.add(backtest)
    db.flush()
    db.add(
        ExperimentTrial(
            backtest_id=backtest.id,
            data_snapshot_id=snapshot_id,
            strategy_id=version.strategy_id,
            universe_key=_universe_key(params.get("universe_snapshot") or []),
            strategy_family=(strategy.family_id if strategy else version.strategy_id),
            parameters=dict(bt_params),
            parameter_hash=canonical_hash(
                {
                    "strategy_version_id": str(version.id),
                    "start_date": str(start),
                    "end_date": str(end),
                    **hash_extra,
                }
            ),
        )
    )
    db.commit()
    executed = execute_backtest(str(backtest.id), record_gates=False)
    if executed.get("status") != "COMPLETED":
        message = executed.get("error") or executed.get("message") or "参数扫描回测失败"
        raise _ScanFailed("scan_backtest_failed", str(message))
    db.expire_all()
    points = (
        db.query(BacktestEquity)
        .filter(BacktestEquity.backtest_id == backtest.id)
        .order_by(BacktestEquity.ts.asc())
        .all()
    )
    equity = [{"ts": row.ts, "strategy_value": row.strategy_value} for row in points]
    return backtest, equity


def _finish_validation(db, run: ValidationRun, payload: dict, *, passed: bool, log_event: str, **log_fields) -> dict:
    run.result = payload
    run.passed = passed
    run.error = None
    run.status = ValidationRunStatus.COMPLETED
    run.progress_step = "Completed"
    run.finished_at = datetime.now(timezone.utc)
    db.flush()
    from services.api.services.validation import maybe_apply_validated

    maybe_apply_validated(
        db, strategy_id=run.strategy_id, strategy_version_id=run.strategy_version_id
    )
    db.commit()
    log.info(log_event, passed=passed, **log_fields)
    return {"status": "COMPLETED", "passed": passed, "run_id": str(run.id)}



def execute_walk_forward(run_id: str) -> dict:
    """One LEAN run per fold over [is_start, oos_end], then score concatenated OOS."""
    from quant.validation.walk_forward import (
        FoldObservation,
        WalkForwardError,
        WalkForwardFold,
        score_walk_forward,
        slice_equity,
    )

    settings = get_settings()
    structlog.contextvars.bind_contextvars(validation_run_id=run_id)
    db = SessionLocal()
    try:
        run = db.get(ValidationRun, UUID(run_id))
        if not run:
            return {"error": "not_found"}
        run.status = ValidationRunStatus.RUNNING
        run.progress_step = "Preparing environment"
        db.commit()

        version = db.get(StrategyVersion, run.strategy_version_id) if run.strategy_version_id else None
        if version is None:
            return _fail_walk_forward(db, run, "version_missing", "策略版本不存在")

        params = dict(run.params or {})
        try:
            folds = [
                WalkForwardFold(
                    index=int(item["index"]),
                    is_start=date.fromisoformat(str(item["is_start"])[:10]),
                    is_end=date.fromisoformat(str(item["is_end"])[:10]),
                    oos_start=date.fromisoformat(str(item["oos_start"])[:10]),
                    oos_end=date.fromisoformat(str(item["oos_end"])[:10]),
                )
                for item in (params.get("folds") or [])
            ]
        except (KeyError, TypeError, ValueError) as exc:
            return _fail_walk_forward(db, run, "folds_invalid", f"fold 参数无法解析：{exc}")
        if len(folds) < 2:
            return _fail_walk_forward(db, run, "folds_missing", "任务参数里没有完整的 fold 列表")

        data_root = Path(settings.data_root)
        snap = None
        snapshot_id = params.get("data_snapshot_id")
        if snapshot_id:
            snap = db.get(DataSnapshot, UUID(str(snapshot_id)))
            if snap:
                candidate = Path(settings.data_root) / "snapshots" / snap.snapshot_key
                if candidate.exists():
                    data_root = candidate
        try:
            universe, memberships = resolve_execution_universe(
                universe_snapshot=params.get("universe_snapshot"),
                snapshot_symbols=snap.symbols if snap else None,
                config=version.config,
            )
        except ValueError as exc:
            return _fail_walk_forward(db, run, "universe_missing", str(exc))

        engine = LeanQuantEngine(
            lean_image=settings.lean_image,
            data_root=data_root,
            jobs_root=Path(settings.jobs_root),
        )
        engine.risk_free_rate = settings.risk_free_rate
        class_name = DEFAULT_STRATEGY_CLASS
        if isinstance(version.config, dict):
            class_name = version.config.get("class_name", DEFAULT_STRATEGY_CLASS)

        observations: list[FoldObservation] = []
        for fold in folds:
            run.progress_step = (
                f"Fold {fold.index + 1}/{len(folds)}: {fold.is_start.isoformat()} → "
                f"{fold.oos_end.isoformat()}"
            )
            db.commit()

            def on_progress(step: str, *, _fold=fold, _n=len(folds)) -> None:
                run.progress_step = f"Fold {_fold.index + 1}/{_n}: {step}"
                db.commit()

            request = BacktestRequest(
                backtest_id=f"wf-{run_id}-f{fold.index}",
                strategy_code=version.code,
                strategy_class_name=class_name,
                start_date=fold.is_start,
                end_date=fold.oos_end,
                benchmark=str(params.get("benchmark") or "SPY"),
                initial_capital=float(params.get("initial_capital") or 100_000.0),
                parameters=dict(params.get("parameters") or {}),
                universe=universe,
                memberships=memberships,
                data_root=data_root,
                timeout_seconds=settings.lean_timeout_seconds,
            )
            try:
                result = engine.run_backtest(request, on_progress=on_progress)
            except BacktestCancelled as exc:
                return _fail_walk_forward(db, run, "cancelled", str(exc))
            except EngineTimeout as exc:
                return _fail_walk_forward(db, run, "engine_timeout", str(exc))
            except Exception as exc:  # noqa: BLE001 - persist failure for UI
                return _fail_walk_forward(db, run, "engine_error", str(exc))

            observations.append(
                FoldObservation(
                    fold=fold,
                    is_equity=slice_equity(result.equity, fold.is_start, fold.is_end),
                    oos_equity=slice_equity(result.equity, fold.oos_start, fold.oos_end),
                )
            )

        try:
            score = score_walk_forward(observations)
        except WalkForwardError as exc:
            return _fail_walk_forward(db, run, "walk_forward_failed", str(exc))

        run.result = score.to_dict()
        run.passed = score.passed
        run.error = None
        run.status = ValidationRunStatus.COMPLETED
        run.progress_step = "Completed"
        run.finished_at = datetime.now(timezone.utc)
        db.flush()
        from services.api.services.validation import maybe_apply_validated

        maybe_apply_validated(
            db, strategy_id=run.strategy_id, strategy_version_id=run.strategy_version_id
        )
        db.commit()
        log.info("walk_forward_completed", passed=score.passed, n_folds=score.n_folds)
        return {"status": "COMPLETED", "passed": score.passed, "run_id": run_id}
    finally:
        db.close()
        structlog.contextvars.unbind_contextvars("validation_run_id")


@celery_app.task(name="backtests.run")
def run_backtest_task(backtest_id: str) -> dict:
    return execute_backtest(backtest_id)


@celery_app.task(name="validation.walk_forward")
def run_walk_forward_task(run_id: str) -> dict:
    return execute_walk_forward(run_id)


def execute_pbo_scan(run_id: str) -> dict:
    """Run one LEAN backtest per lookback, then CSCV on the aligned return matrix."""
    from quant.metrics.pbo import (
        LOOKBACK_PARAMETER,
        PBOScanError,
        align_return_matrix,
        assert_configs_differ,
        choose_n_slices,
        combinatorially_symmetric_cv,
        daily_returns_from_equity,
    )

    structlog.contextvars.bind_contextvars(validation_run_id=run_id)
    db = SessionLocal()
    try:
        run = db.get(ValidationRun, UUID(run_id))
        if not run:
            return {"error": "not_found"}
        run.status = ValidationRunStatus.RUNNING
        run.progress_step = "Preparing parameter scan"
        db.commit()

        version = db.get(StrategyVersion, run.strategy_version_id) if run.strategy_version_id else None
        if version is None:
            return _fail_walk_forward(db, run, "version_missing", "策略版本不存在")

        params = dict(run.params or {})
        try:
            values = [int(v) for v in (params.get("values") or [])]
            start = date.fromisoformat(str(params["start_date"]))
            end = date.fromisoformat(str(params["end_date"]))
        except (KeyError, TypeError, ValueError) as exc:
            return _fail_walk_forward(db, run, "params_invalid", f"扫描参数无法解析：{exc}")
        if len(values) < 2:
            return _fail_walk_forward(db, run, "values_missing", "扫描至少需要 2 个参数值")

        snapshot_id = None
        if params.get("data_snapshot_id"):
            snapshot_id = UUID(str(params["data_snapshot_id"]))
        series = []
        config_rows: list[dict[str, object]] = []
        backtest_ids: list[str] = []

        try:
            for index, value in enumerate(values):
                run.progress_step = f"Config {index + 1}/{len(values)}: lookback={value}"
                db.commit()
                bt_params = dict(params.get("base_parameters") or {})
                bt_params[LOOKBACK_PARAMETER] = value
                backtest, equity = _run_scan_backtest(
                    db,
                    version=version,
                    start=start,
                    end=end,
                    params=params,
                    bt_params=bt_params,
                    snapshot_id=snapshot_id,
                    hash_extra={LOOKBACK_PARAMETER: value},
                )
                try:
                    dates, rets = daily_returns_from_equity(equity)
                except PBOScanError as exc:
                    return _fail_walk_forward(db, run, "returns_failed", str(exc))
                series.append((dates, rets))
                backtest_ids.append(str(backtest.id))
                metrics = db.get(BacktestMetrics, backtest.id)
                config_rows.append(
                    {
                        LOOKBACK_PARAMETER: value,
                        "backtest_id": str(backtest.id),
                        "sharpe": metrics.sharpe if metrics else None,
                    }
                )
        except _ScanFailed as exc:
            return _fail_walk_forward(db, run, exc.code, exc.message)

        try:
            _dates, matrix = align_return_matrix(series)
            assert_configs_differ(matrix)
            n_slices = choose_n_slices(int(matrix.shape[0]))
            pbo = combinatorially_symmetric_cv(matrix, n_slices=n_slices)
        except (PBOScanError, ValueError) as exc:
            return _fail_walk_forward(db, run, "pbo_failed", str(exc))

        payload = pbo.to_dict()
        payload["backtest_ids"] = backtest_ids
        payload["configs"] = config_rows
        payload["n_obs_aligned"] = int(matrix.shape[0])
        return _finish_validation(
            db, run, payload, passed=bool(pbo.passed), log_event="pbo_scan_completed", pbo=pbo.pbo
        )
    finally:
        db.close()
        structlog.contextvars.unbind_contextvars("validation_run_id")


@celery_app.task(name="validation.pbo")
def run_pbo_scan_task(run_id: str) -> dict:
    return execute_pbo_scan(run_id)


def execute_sensitivity_scan(run_id: str) -> dict:
    """Run one LEAN backtest per lookback, then classify the Sharpe surface."""
    from quant.metrics.pbo import LOOKBACK_PARAMETER
    from quant.validation.sensitivity import SensitivityError, assert_navs_differ, classify_surface

    structlog.contextvars.bind_contextvars(validation_run_id=run_id)
    db = SessionLocal()
    try:
        run = db.get(ValidationRun, UUID(run_id))
        if not run:
            return {"error": "not_found"}
        run.status = ValidationRunStatus.RUNNING
        run.progress_step = "Preparing sensitivity scan"
        db.commit()

        version = db.get(StrategyVersion, run.strategy_version_id) if run.strategy_version_id else None
        if version is None:
            return _fail_walk_forward(db, run, "version_missing", "策略版本不存在")

        params = dict(run.params or {})
        try:
            values = [int(v) for v in (params.get("values") or [])]
            start = date.fromisoformat(str(params["start_date"]))
            end = date.fromisoformat(str(params["end_date"]))
        except (KeyError, TypeError, ValueError) as exc:
            return _fail_walk_forward(db, run, "params_invalid", f"扫描参数无法解析：{exc}")
        if len(values) < 3:
            return _fail_walk_forward(db, run, "values_missing", "敏感性至少需要 3 个参数值")

        snapshot_id = None
        if params.get("data_snapshot_id"):
            snapshot_id = UUID(str(params["data_snapshot_id"]))
        sharpes: list[float | None] = []
        finals: list[float | None] = []
        backtest_ids: list[str] = []

        try:
            for index, value in enumerate(values):
                run.progress_step = f"Config {index + 1}/{len(values)}: lookback={value}"
                db.commit()
                bt_params = dict(params.get("base_parameters") or {})
                bt_params[LOOKBACK_PARAMETER] = value
                backtest, _equity = _run_scan_backtest(
                    db,
                    version=version,
                    start=start,
                    end=end,
                    params=params,
                    bt_params=bt_params,
                    snapshot_id=snapshot_id,
                    hash_extra={LOOKBACK_PARAMETER: value, "scan": "sensitivity"},
                )
                backtest_ids.append(str(backtest.id))
                metrics = db.get(BacktestMetrics, backtest.id)
                sharpes.append(metrics.sharpe if metrics else None)
                finals.append(metrics.final_equity if metrics else None)
        except _ScanFailed as exc:
            return _fail_walk_forward(db, run, exc.code, exc.message)

        try:
            assert_navs_differ(finals)
            result = classify_surface(values, sharpes, backtest_ids=backtest_ids)
        except SensitivityError as exc:
            return _fail_walk_forward(db, run, "sensitivity_failed", str(exc))

        payload = result.to_dict()
        payload["backtest_ids"] = backtest_ids
        return _finish_validation(
            db,
            run,
            payload,
            passed=result.passed,
            log_event="sensitivity_scan_completed",
            shape=result.shape,
        )
    finally:
        db.close()
        structlog.contextvars.unbind_contextvars("validation_run_id")


@celery_app.task(name="validation.sensitivity")
def run_sensitivity_scan_task(run_id: str) -> dict:
    return execute_sensitivity_scan(run_id)


def execute_cost_scan(run_id: str) -> dict:
    """Sweep one-way slippage in bps and find where CAPM alpha hits zero."""
    from quant.validation.cost import (
        DEFAULT_REALISTIC_BPS,
        FEE_PARAMETER,
        SLIPPAGE_PARAMETER,
        CostSensitivityError,
        assert_cost_paths_differ,
        classify_cost_curve,
    )

    structlog.contextvars.bind_contextvars(validation_run_id=run_id)
    db = SessionLocal()
    try:
        run = db.get(ValidationRun, UUID(run_id))
        if not run:
            return {"error": "not_found"}
        run.status = ValidationRunStatus.RUNNING
        run.progress_step = "Preparing cost scan"
        db.commit()

        version = db.get(StrategyVersion, run.strategy_version_id) if run.strategy_version_id else None
        if version is None:
            return _fail_walk_forward(db, run, "version_missing", "策略版本不存在")

        params = dict(run.params or {})
        try:
            costs = [float(v) for v in (params.get("costs_bps") or [])]
            start = date.fromisoformat(str(params["start_date"]))
            end = date.fromisoformat(str(params["end_date"]))
            realistic = float(params.get("realistic_one_way_bps", DEFAULT_REALISTIC_BPS))
        except (KeyError, TypeError, ValueError) as exc:
            return _fail_walk_forward(db, run, "params_invalid", f"成本参数无法解析：{exc}")
        if len(costs) < 3:
            return _fail_walk_forward(db, run, "values_missing", "成本扫描至少需要 3 个点")

        snapshot_id = None
        if params.get("data_snapshot_id"):
            snapshot_id = UUID(str(params["data_snapshot_id"]))
        alphas: list[float | None] = []
        sharpes: list[float | None] = []
        finals: list[float | None] = []
        backtest_ids: list[str] = []
        traded = False

        try:
            for index, cost in enumerate(costs):
                run.progress_step = f"Cost {index + 1}/{len(costs)}: {cost:g} bps"
                db.commit()
                bt_params = dict(params.get("base_parameters") or {})
                bt_params[SLIPPAGE_PARAMETER] = cost
                bt_params[FEE_PARAMETER] = 0.0
                backtest, _equity = _run_scan_backtest(
                    db,
                    version=version,
                    start=start,
                    end=end,
                    params=params,
                    bt_params=bt_params,
                    snapshot_id=snapshot_id,
                    hash_extra={SLIPPAGE_PARAMETER: cost, FEE_PARAMETER: 0.0, "scan": "cost"},
                )
                backtest_ids.append(str(backtest.id))
                metrics = db.get(BacktestMetrics, backtest.id)
                alphas.append(metrics.alpha_capm if metrics else None)
                sharpes.append(metrics.sharpe if metrics else None)
                finals.append(metrics.final_equity if metrics else None)
                if metrics is not None and (metrics.trade_count or 0) > 0:
                    traded = True
        except _ScanFailed as exc:
            return _fail_walk_forward(db, run, exc.code, exc.message)

        try:
            assert_cost_paths_differ(finals, traded=traded)
            result = classify_cost_curve(
                costs,
                alphas,
                sharpes=sharpes,
                backtest_ids=backtest_ids,
                realistic_one_way_bps=realistic,
            )
        except CostSensitivityError as exc:
            return _fail_walk_forward(db, run, "cost_failed", str(exc))

        payload = result.to_dict()
        payload["backtest_ids"] = backtest_ids
        payload["traded"] = traded
        return _finish_validation(
            db,
            run,
            payload,
            passed=result.passed,
            log_event="cost_scan_completed",
            breakeven_bps=result.breakeven_bps,
        )
    finally:
        db.close()
        structlog.contextvars.unbind_contextvars("validation_run_id")


@celery_app.task(name="validation.cost")
def run_cost_scan_task(run_id: str) -> dict:
    return execute_cost_scan(run_id)



def execute_bootstrap(run_id: str) -> dict:
    """Stationary bootstrap on an existing completed backtest equity path. No LEAN."""
    from quant.validation.bootstrap import BootstrapError, bootstrap_from_equity
    from services.api.services.validation import _bootstrap_seed, equity_payload

    structlog.contextvars.bind_contextvars(validation_run_id=run_id)
    db = SessionLocal()
    try:
        run = db.get(ValidationRun, UUID(run_id))
        if not run:
            return {"error": "not_found"}
        run.status = ValidationRunStatus.RUNNING
        run.progress_step = "Resampling returns"
        db.commit()
        if run.backtest_id is None:
            return _fail_walk_forward(db, run, "backtest_missing", "Bootstrap 需要一次已完成的回测")
        backtest = db.get(Backtest, run.backtest_id)
        if backtest is None or backtest.status != BacktestStatus.COMPLETED:
            return _fail_walk_forward(db, run, "backtest_missing", "Bootstrap 需要一次已完成的回测")
        params = dict(run.params or {})
        try:
            n_boot = int(params.get("n_boot") or 2000)
            confidence = float(params.get("confidence_level") or 0.95)
            method = str(params.get("method") or "stationary")
            raw_block = params.get("mean_block_length")
            mean_block = float(raw_block) if raw_block is not None else None
            seed = params.get("seed")
            resolved_seed = _bootstrap_seed(backtest, int(seed) if seed is not None else None)
        except (TypeError, ValueError) as exc:
            return _fail_walk_forward(db, run, "params_invalid", f"Bootstrap 参数无法解析：{exc}")
        points = equity_payload(db, backtest.id)
        try:
            result = bootstrap_from_equity(
                points,
                n_boot=n_boot,
                confidence_level=confidence,
                method=method,
                mean_block_length=mean_block,
                seed=resolved_seed,
            )
        except BootstrapError as exc:
            return _fail_walk_forward(db, run, "bootstrap_failed", str(exc))
        payload = result.to_dict()
        run.params = {
            **params,
            "seed": resolved_seed,
            "mean_block_length": result.mean_block_length,
        }
        return _finish_validation(
            db,
            run,
            payload,
            passed=result.passed,
            log_event="bootstrap_completed",
            sharpe_low=result.sharpe.low,
        )
    finally:
        db.close()
        structlog.contextvars.unbind_contextvars("validation_run_id")


@celery_app.task(name="validation.bootstrap")
def run_bootstrap_task(run_id: str) -> dict:
    return execute_bootstrap(run_id)


def execute_regime(run_id: str) -> dict:
    """Slice an existing completed backtest by market regime. No LEAN."""
    from quant.validation.regime import RegimeError, score_regime
    from services.api.services.validation import equity_payload

    structlog.contextvars.bind_contextvars(validation_run_id=run_id)
    db = SessionLocal()
    try:
        run = db.get(ValidationRun, UUID(run_id))
        if not run:
            return {"error": "not_found"}
        run.status = ValidationRunStatus.RUNNING
        run.progress_step = "Slicing regimes"
        db.commit()
        if run.backtest_id is None:
            return _fail_walk_forward(db, run, "backtest_missing", "制度检验需要一次已完成的回测")
        backtest = db.get(Backtest, run.backtest_id)
        if backtest is None or backtest.status != BacktestStatus.COMPLETED:
            return _fail_walk_forward(db, run, "backtest_missing", "制度检验需要一次已完成的回测")
        points = equity_payload(db, backtest.id)
        try:
            result = score_regime(points)
        except RegimeError as exc:
            return _fail_walk_forward(db, run, "regime_failed", str(exc))
        payload = result.to_dict()
        return _finish_validation(
            db,
            run,
            payload,
            passed=result.passed,
            log_event="regime_completed",
            single_regime=result.single_regime,
        )
    finally:
        db.close()
        structlog.contextvars.unbind_contextvars("validation_run_id")


@celery_app.task(name="validation.regime")
def run_regime_task(run_id: str) -> dict:
    return execute_regime(run_id)


def execute_spa(run_id: str) -> dict:
    """White RC / Hansen SPA on the family trial ledger. No extra LEAN run."""
    from quant.validation.spa import (
        DEFAULT_ALPHA,
        DEFAULT_N_BOOT,
        SpaError,
        panel_from_equity_paths,
        spa_test,
    )
    from services.api.services.validation import _spa_seed, load_spa_paths

    structlog.contextvars.bind_contextvars(validation_run_id=run_id)
    db = SessionLocal()
    try:
        run = db.get(ValidationRun, UUID(run_id))
        if not run:
            return {"error": "not_found"}
        run.status = ValidationRunStatus.RUNNING
        run.progress_step = "Reality Check"
        db.commit()
        if run.backtest_id is None:
            return _fail_walk_forward(db, run, "backtest_missing", "Reality Check 需要一次已完成的回测作为模板")
        backtest = db.get(Backtest, run.backtest_id)
        if backtest is None or backtest.status != BacktestStatus.COMPLETED:
            return _fail_walk_forward(db, run, "backtest_missing", "Reality Check 需要一次已完成的回测作为模板")
        params = dict(run.params or {})
        try:
            n_boot = int(params.get("n_boot") or DEFAULT_N_BOOT)
            alpha = float(params.get("alpha") or DEFAULT_ALPHA)
            seed = params.get("seed")
            resolved_seed = _spa_seed(backtest, int(seed) if seed is not None else None)
            raw_family = params.get("family_id")
            raw_snapshot = params.get("data_snapshot_id")
            if raw_family:
                family_id = UUID(str(raw_family))
            else:
                version = db.get(StrategyVersion, run.strategy_version_id) if run.strategy_version_id else None
                strategy = db.get(Strategy, version.strategy_id) if version is not None else None
                if strategy is None:
                    return _fail_walk_forward(db, run, "family_missing", "找不到策略家族，无法对齐试验台账")
                family_id = strategy.family_id or strategy.id
            snapshot_id = UUID(str(raw_snapshot)) if raw_snapshot else backtest.data_snapshot_id
        except (TypeError, ValueError) as exc:
            return _fail_walk_forward(db, run, "params_invalid", f"SPA 参数无法解析：{exc}")
        try:
            paths = load_spa_paths(db, family_id=family_id, snapshot_id=snapshot_id)
            panel, ids = panel_from_equity_paths(paths)
            result = spa_test(
                panel,
                n_boot=n_boot,
                alpha=alpha,
                seed=resolved_seed,
                ids=ids,
            )
        except SpaError as exc:
            return _fail_walk_forward(db, run, "spa_failed", str(exc))
        payload = result.to_dict()
        run.params = {
            **params,
            "seed": resolved_seed,
            "mean_block_length": result.mean_block_length,
            "n_models": result.n_models,
            "family_id": str(family_id),
            "data_snapshot_id": str(snapshot_id) if snapshot_id else None,
        }
        return _finish_validation(
            db,
            run,
            payload,
            passed=result.passed,
            log_event="spa_completed",
            p_spa_c=result.p_spa_consistent,
            n_models=result.n_models,
        )
    finally:
        db.close()
        structlog.contextvars.unbind_contextvars("validation_run_id")


@celery_app.task(name="validation.spa")
def run_spa_task(run_id: str) -> dict:
    return execute_spa(run_id)


@celery_app.task(name="data.ingest")
def run_ingest_task(job_id: str) -> dict:
    from services.api.services.ingest_jobs import execute_ingest_job

    return execute_ingest_job(job_id)


@celery_app.task(name="data.reconcile_market")
def reconcile_market_data_task(force: bool = False) -> dict:
    """Periodic full re-pull of the current universe to catch vendor restatements."""
    from services.api.services.ingest_jobs import schedule_market_reconcile

    return schedule_market_reconcile(force=force, scheduled=True)


@celery_app.task(name="backtests.reconcile_orphans")
def reconcile_orphan_backtests_task() -> int:
    return reconcile_orphan_backtests()


@celery_app.task(name="worker.publish_health")
def publish_health_task() -> dict:
    from services.worker.health import publish_worker_health

    return publish_worker_health()
