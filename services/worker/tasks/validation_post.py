"""Post-hoc validation kinds: stationary bootstrap, regime scoring, Hansen SPA.

These three operate on equity paths already stored for a completed backtest
(the trial ledger for SPA) and never launch a LEAN run.
"""

from __future__ import annotations

from uuid import UUID

import structlog

from services.api.models import (
    Backtest,
    BacktestStatus,
    Strategy,
    StrategyVersion,
    ValidationRun,
    ValidationRunStatus,
)
from services.worker import tasks as _tasks
from services.worker.celery_app import celery_app

from .scans import _fail_walk_forward, _finish_validation


def execute_bootstrap(run_id: str) -> dict:
    """Stationary bootstrap on an existing completed backtest equity path. No LEAN."""
    from quant.validation.bootstrap import BootstrapError, bootstrap_from_equity
    from services.api.services.validation import _bootstrap_seed, equity_payload

    structlog.contextvars.bind_contextvars(validation_run_id=run_id)
    db = _tasks.SessionLocal()
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
    db = _tasks.SessionLocal()
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
    db = _tasks.SessionLocal()
    try:
        run = db.get(ValidationRun, UUID(run_id))
        if not run:
            return {"error": "not_found"}
        run.status = ValidationRunStatus.RUNNING
        run.progress_step = "Reality Check"
        db.commit()
        if run.backtest_id is None:
            return _fail_walk_forward(
                db, run, "backtest_missing", "Reality Check 需要一次已完成的回测作为模板"
            )
        backtest = db.get(Backtest, run.backtest_id)
        if backtest is None or backtest.status != BacktestStatus.COMPLETED:
            return _fail_walk_forward(
                db, run, "backtest_missing", "Reality Check 需要一次已完成的回测作为模板"
            )
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
                version = (
                    db.get(StrategyVersion, run.strategy_version_id)
                    if run.strategy_version_id
                    else None
                )
                strategy = db.get(Strategy, version.strategy_id) if version is not None else None
                if strategy is None:
                    return _fail_walk_forward(
                        db, run, "family_missing", "找不到策略家族，无法对齐试验台账"
                    )
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
