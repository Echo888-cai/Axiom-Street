"""LEAN-scanning validation kinds: walk-forward, PBO, sensitivity, cost.

Each validator builds a config set, runs backtests through the shared scan
machinery in ``scans.py``, then scores with a ``quant/validation/*`` scorer and
finishes the run via ``_finish_validation``. Runtime DB/engine dependencies
resolve through the package namespace (see ``_common`` module docstring).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

import structlog

from quant.engine.base import BacktestRequest
from quant.engine.errors import BacktestCancelled, EngineTimeout
from quant.strategy_sdk.spy_200dma import DEFAULT_STRATEGY_CLASS
from services.api.models import (
    BacktestMetrics,
    DataSnapshot,
    StrategyVersion,
    ValidationRun,
    ValidationRunStatus,
)
from services.api.settings import get_settings
from services.worker import tasks as _tasks
from services.worker.celery_app import celery_app

from ._common import log, resolve_execution_universe
from .risk_config import resolve_risk_config_json
from .scans import (
    _fail_walk_forward,
    _finish_validation,
    _run_scan_configs,
    _ScanFailed,
)


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
    db = _tasks.SessionLocal()
    try:
        run = db.get(ValidationRun, UUID(run_id))
        if not run:
            return {"error": "not_found"}
        run.status = ValidationRunStatus.RUNNING
        run.progress_step = "Preparing environment"
        db.commit()

        version = (
            db.get(StrategyVersion, run.strategy_version_id) if run.strategy_version_id else None
        )
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

        engine = _tasks.LeanQuantEngine(
            lean_image=settings.lean_image,
            data_root=data_root,
            jobs_root=Path(settings.jobs_root),
        )
        engine.risk_free_rate = settings.risk_free_rate
        class_name = DEFAULT_STRATEGY_CLASS
        if isinstance(version.config, dict):
            class_name = version.config.get("class_name", DEFAULT_STRATEGY_CLASS)

        try:
            risk_config_json = resolve_risk_config_json(version.config)
        except ValueError as exc:
            return _fail_walk_forward(db, run, "risk_limits_invalid", str(exc))

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
                risk_config_json=risk_config_json,
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
    db = _tasks.SessionLocal()
    try:
        run = db.get(ValidationRun, UUID(run_id))
        if not run:
            return {"error": "not_found"}
        run.status = ValidationRunStatus.RUNNING
        run.progress_step = "Preparing parameter scan"
        db.commit()

        version = (
            db.get(StrategyVersion, run.strategy_version_id) if run.strategy_version_id else None
        )
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

        series = []
        config_rows: list[dict[str, object]] = []
        backtest_ids: list[str] = []

        try:
            jobs = []
            for value in values:
                bt_params = dict(params.get("base_parameters") or {})
                bt_params[LOOKBACK_PARAMETER] = value
                jobs.append((bt_params, {LOOKBACK_PARAMETER: value}))

            def _progress(index: int, total: int, bt_params: dict) -> None:
                run.progress_step = (
                    f"Config {index + 1}/{total}: lookback={bt_params.get(LOOKBACK_PARAMETER)}"
                )
                db.commit()

            scanned = _run_scan_configs(
                version_id=version.id,
                start=start,
                end=end,
                params=params,
                jobs=jobs,
                on_progress=_progress,
            )
            for (bt_params, _extra), (backtest, equity) in zip(jobs, scanned):
                try:
                    dates, rets = daily_returns_from_equity(equity)
                except PBOScanError as exc:
                    return _fail_walk_forward(db, run, "returns_failed", str(exc))
                series.append((dates, rets))
                backtest_ids.append(str(backtest.id))
                metrics = db.get(BacktestMetrics, backtest.id)
                config_rows.append(
                    {
                        LOOKBACK_PARAMETER: bt_params[LOOKBACK_PARAMETER],
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
    db = _tasks.SessionLocal()
    try:
        run = db.get(ValidationRun, UUID(run_id))
        if not run:
            return {"error": "not_found"}
        run.status = ValidationRunStatus.RUNNING
        run.progress_step = "Preparing sensitivity scan"
        db.commit()

        version = (
            db.get(StrategyVersion, run.strategy_version_id) if run.strategy_version_id else None
        )
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

        sharpes: list[float | None] = []
        finals: list[float | None] = []
        backtest_ids: list[str] = []

        try:
            jobs = []
            for value in values:
                bt_params = dict(params.get("base_parameters") or {})
                bt_params[LOOKBACK_PARAMETER] = value
                jobs.append((bt_params, {LOOKBACK_PARAMETER: value, "scan": "sensitivity"}))

            def _progress(index: int, total: int, bt_params: dict) -> None:
                run.progress_step = (
                    f"Config {index + 1}/{total}: lookback={bt_params.get(LOOKBACK_PARAMETER)}"
                )
                db.commit()

            scanned = _run_scan_configs(
                version_id=version.id,
                start=start,
                end=end,
                params=params,
                jobs=jobs,
                on_progress=_progress,
            )
            for backtest, _equity in scanned:
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
    db = _tasks.SessionLocal()
    try:
        run = db.get(ValidationRun, UUID(run_id))
        if not run:
            return {"error": "not_found"}
        run.status = ValidationRunStatus.RUNNING
        run.progress_step = "Preparing cost scan"
        db.commit()

        version = (
            db.get(StrategyVersion, run.strategy_version_id) if run.strategy_version_id else None
        )
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

        alphas: list[float | None] = []
        sharpes: list[float | None] = []
        finals: list[float | None] = []
        backtest_ids: list[str] = []
        traded = False

        try:
            jobs = []
            for cost in costs:
                bt_params = dict(params.get("base_parameters") or {})
                bt_params[SLIPPAGE_PARAMETER] = cost
                bt_params[FEE_PARAMETER] = 0.0
                jobs.append(
                    (
                        bt_params,
                        {SLIPPAGE_PARAMETER: cost, FEE_PARAMETER: 0.0, "scan": "cost"},
                    )
                )

            def _progress(index: int, total: int, bt_params: dict) -> None:
                run.progress_step = (
                    f"Cost {index + 1}/{total}: {bt_params.get(SLIPPAGE_PARAMETER):g} bps"
                )
                db.commit()

            scanned = _run_scan_configs(
                version_id=version.id,
                start=start,
                end=end,
                params=params,
                jobs=jobs,
                on_progress=_progress,
            )
            for backtest, _equity in scanned:
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
