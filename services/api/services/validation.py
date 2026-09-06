"""Phase 3 validation runs. DSR, walk-forward, PBO, sensitivity, cost, bootstrap, regime, and SPA gate VALIDATED."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from quant.metrics.deflated_sharpe import (
    DSR_PASS_THRESHOLD,
    deflated_sharpe_ratio,
    pearson_kurtosis,
    trials_stdev_from_sharpes,
)
from quant.validation.bootstrap import (
    DEFAULT_CONFIDENCE,
    DEFAULT_N_BOOT,
    BootstrapError,
    bootstrap_from_equity,
)
from quant.validation.regime import (
    BEAR_DRAWDOWN,
    MIN_AXIS_OBS,
    VOL_WINDOW,
    RegimeError,
    score_regime,
)
from quant.validation.spa import SpaError
from quant.validation.walk_forward import WalkForwardError
from services.api.models import (
    AuditLog,
    Backtest,
    BacktestEquity,
    BacktestMetrics,
    BacktestStatus,
    ExperimentTrial,
    Strategy,
    StrategyStatus,
    StrategyVersion,
    ValidationKind,
    ValidationRun,
    ValidationRunStatus,
)
from services.api.schemas import ValidationCreate, ValidationRunOut
from services.api.services.strategies import get_version
from services.api.services.validation_spec import (
    engine_kinds,
    get_spec,
    validated_kinds,
)
from services.api.settings import get_settings

_BT_INFLIGHT = {BacktestStatus.QUEUED, BacktestStatus.STARTING, BacktestStatus.RUNNING}
_WF_INFLIGHT = {ValidationRunStatus.QUEUED, ValidationRunStatus.RUNNING}
_ENGINE_KINDS = engine_kinds()
_VALIDATED_KINDS = validated_kinds()
_LIVE_STATUSES = {
    StrategyStatus.PAPER,
    StrategyStatus.APPROVED,
    StrategyStatus.LIVE,
    StrategyStatus.PAUSED,
    StrategyStatus.ARCHIVED,
}


def record_dsr_for_backtest(
    db: Session,
    backtest: Backtest,
    metrics: dict[str, Any],
    *,
    n_obs: int,
    periods_per_year: float = 252.0,
) -> dict[str, Any]:
    """Compute DSR from the trial ledger and persist a validation_run.

    Missing inputs fail loud into the validation row — they do not invent a
    passing DSR. Walk-forward OOS rows (``is_oos``) are not trials.
    """
    strategy_id = None
    family_id = None
    version = backtest.strategy_version
    if version is not None:
        strategy_id = version.strategy_id
        strategy = db.get(Strategy, version.strategy_id) if version.strategy_id else None
        if strategy is not None:
            family_id = strategy.family_id or strategy.id

    trials = []
    if family_id is not None:
        query = select(ExperimentTrial).where(ExperimentTrial.strategy_family == family_id)
        query = query.where(
            or_(ExperimentTrial.is_oos.is_(False), ExperimentTrial.is_oos.is_(None))
        )
        if backtest.data_snapshot_id is not None:
            query = query.where(ExperimentTrial.data_snapshot_id == backtest.data_snapshot_id)
        trials = list(db.scalars(query).all())
    sharpes = [t.observed_sharpe for t in trials if t.observed_sharpe is not None]
    n_trials = max(len(sharpes), 1)

    params = {
        "n_obs": n_obs,
        "n_trials": n_trials,
        "periods_per_year": periods_per_year,
        "pass_threshold": DSR_PASS_THRESHOLD,
        "family_id": str(family_id) if family_id else None,
        "data_snapshot_id": str(backtest.data_snapshot_id) if backtest.data_snapshot_id else None,
    }
    run = ValidationRun(
        strategy_id=strategy_id,
        strategy_version_id=backtest.strategy_version_id,
        backtest_id=backtest.id,
        kind=ValidationKind.DSR,
        status=ValidationRunStatus.COMPLETED,
        progress_step="Completed",
        params=params,
        result={},
        passed=False,
        finished_at=datetime.now(timezone.utc),
    )

    sharpe = metrics.get("sharpe")
    if sharpe is None or n_obs < 2:
        run.error = {
            "code": "dsr_inputs_missing",
            "message": "缺少 Sharpe 或收益观测数，拒绝计算 DSR。",
        }
        db.add(run)
        return {}

    try:
        sr_period = float(sharpe) / math.sqrt(periods_per_year)
        std_ann = trials_stdev_from_sharpes([float(x) for x in sharpes] or [float(sharpe)])
        std_period = std_ann / math.sqrt(periods_per_year)
        skew = float(metrics["skewness"]) if metrics.get("skewness") is not None else 0.0
        excess = metrics.get("kurtosis")
        kurtosis = pearson_kurtosis(float(excess) if excess is not None else 0.0)
        result = deflated_sharpe_ratio(
            sr_period,
            n_obs,
            n_trials,
            std_period,
            skewness=skew,
            kurtosis=kurtosis,
        )
    except ValueError as exc:
        run.error = {"code": "dsr_failed", "message": str(exc)}
        db.add(run)
        return {}

    payload = result.to_dict()
    payload["observed_sharpe_annualized"] = float(sharpe)
    run.result = payload
    run.passed = result.passed
    db.add(run)

    row = db.get(BacktestMetrics, backtest.id)
    if row is not None:
        row.deflated_sharpe = result.dsr
        row.probabilistic_sharpe = result.psr
        row.dsr_n_trials = result.n_trials
        row.dsr_sr_star = result.sr_star
        extras = dict(row.extras or {})
        extras["dsr"] = payload
        row.extras = extras
    return {
        "deflated_sharpe": result.dsr,
        "probabilistic_sharpe": result.psr,
        "dsr_n_trials": result.n_trials,
        "dsr_sr_star": result.sr_star,
    }


def _bootstrap_seed(backtest: Backtest, seed: int | None) -> int:
    if seed is not None:
        return int(seed)
    return int(backtest.id.int % (2**32 - 1))


def equity_payload(db: Session, backtest_id: UUID) -> list[dict[str, Any]]:
    points = (
        db.query(BacktestEquity)
        .filter(BacktestEquity.backtest_id == backtest_id)
        .order_by(BacktestEquity.ts.asc())
        .all()
    )
    return [
        {"ts": row.ts, "strategy_value": row.strategy_value, "benchmark_value": row.benchmark_value}
        for row in points
    ]


def record_bootstrap_for_backtest(
    db: Session,
    backtest: Backtest,
    equity: list[dict[str, Any]] | None = None,
    *,
    n_boot: int = DEFAULT_N_BOOT,
    confidence_level: float = DEFAULT_CONFIDENCE,
    method: str = "stationary",
    mean_block_length: float | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Stationary-bootstrap CIs from the backtest equity path.

    Missing or short series fail loud into the validation row — they do not
    invent a passing interval. Scan backtests should not call this.
    """
    strategy_id = None
    version = backtest.strategy_version
    if version is not None:
        strategy_id = version.strategy_id
    resolved_seed = _bootstrap_seed(backtest, seed)
    params: dict[str, Any] = {
        "n_boot": n_boot,
        "confidence_level": confidence_level,
        "method": method,
        "mean_block_length": mean_block_length,
        "seed": resolved_seed,
    }
    run = ValidationRun(
        strategy_id=strategy_id,
        strategy_version_id=backtest.strategy_version_id,
        backtest_id=backtest.id,
        kind=ValidationKind.BOOTSTRAP,
        status=ValidationRunStatus.COMPLETED,
        progress_step="Completed",
        params=params,
        result={},
        passed=False,
        finished_at=datetime.now(timezone.utc),
    )
    points = equity if equity is not None else equity_payload(db, backtest.id)
    try:
        result = bootstrap_from_equity(
            points,
            n_boot=n_boot,
            confidence_level=confidence_level,
            method=method,
            mean_block_length=mean_block_length,
            seed=resolved_seed,
        )
    except BootstrapError as exc:
        run.error = {"code": "bootstrap_failed", "message": str(exc)}
        db.add(run)
        return {}
    payload = result.to_dict()
    run.result = payload
    run.passed = result.passed
    db.add(run)
    return payload


def record_regime_for_backtest(
    db: Session,
    backtest: Backtest,
    equity: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Slice the completed backtest by market regime. No extra LEAN run.

    Missing benchmark or uncovered axes fail loud into the validation row.
    Scan backtests should not call this.
    """
    strategy_id = None
    version = backtest.strategy_version
    if version is not None:
        strategy_id = version.strategy_id
    params: dict[str, Any] = {
        "bear_drawdown": BEAR_DRAWDOWN,
        "vol_window": VOL_WINDOW,
        "min_axis_obs": MIN_AXIS_OBS,
    }
    run = ValidationRun(
        strategy_id=strategy_id,
        strategy_version_id=backtest.strategy_version_id,
        backtest_id=backtest.id,
        kind=ValidationKind.REGIME,
        status=ValidationRunStatus.COMPLETED,
        progress_step="Completed",
        params=params,
        result={},
        passed=False,
        finished_at=datetime.now(timezone.utc),
    )
    points = equity if equity is not None else equity_payload(db, backtest.id)
    try:
        result = score_regime(points)
    except RegimeError as exc:
        run.error = {"code": "regime_failed", "message": str(exc)}
        db.add(run)
        return {}
    payload = result.to_dict()
    run.result = payload
    run.passed = result.passed
    db.add(run)
    return payload


def count_inflight_engine_jobs(db: Session) -> int:
    backtests = int(
        db.scalar(
            select(func.count()).select_from(Backtest).where(Backtest.status.in_(_BT_INFLIGHT))
        )
        or 0
    )
    walks = int(
        db.scalar(
            select(func.count())
            .select_from(ValidationRun)
            .where(
                ValidationRun.kind.in_(list(_ENGINE_KINDS)),
                ValidationRun.status.in_(_WF_INFLIGHT),
            )
        )
        or 0
    )
    return backtests + walks


def list_validation_runs(
    db: Session,
    *,
    strategy_id: UUID | None = None,
    kind: ValidationKind | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ValidationRun], int]:
    query = select(ValidationRun).order_by(ValidationRun.created_at.desc())
    count_q = select(func.count()).select_from(ValidationRun)
    if strategy_id is not None:
        query = query.where(ValidationRun.strategy_id == strategy_id)
        count_q = count_q.where(ValidationRun.strategy_id == strategy_id)
    if kind is not None:
        query = query.where(ValidationRun.kind == kind)
        count_q = count_q.where(ValidationRun.kind == kind)
    total = int(db.scalar(count_q) or 0)
    rows = list(db.scalars(query.offset(offset).limit(limit)).all())
    return rows, total


def get_validation_run(db: Session, run_id: UUID) -> ValidationRun:
    row = db.get(ValidationRun, run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="验证运行不存在")
    return row


def to_out(row: ValidationRun) -> ValidationRunOut:
    kind = row.kind.value if isinstance(row.kind, ValidationKind) else str(row.kind)
    run_status = (
        row.status.value if isinstance(row.status, ValidationRunStatus) else str(row.status)
    )
    return ValidationRunOut(
        id=row.id,
        strategy_id=row.strategy_id,
        strategy_version_id=row.strategy_version_id,
        backtest_id=row.backtest_id,
        kind=kind,
        status=run_status,
        progress_step=row.progress_step,
        params=row.params or {},
        result=row.result or {},
        passed=row.passed,
        error=row.error,
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


def validation_gates() -> dict[str, Any]:
    return {
        "validated_requires": [kind.name for kind in _VALIDATED_KINDS],
        "available": [kind.name for kind in _VALIDATED_KINDS],
        "missing": [],
        "note": (
            "VALIDATED 由系统持有：Walk-forward 通过、同版本 DSR 过 95% 线、"
            "参数扫描 PBO ≤ 0.5、敏感性为高原而非孤峰、临界单边成本高于真实成本、"
            "Sharpe 的 stationary bootstrap 区间下界 > 0、"
            "牛/熊、高/低波动、加息/降息均未塌缩、"
            "且 Hansen SPA_c 在试验台账上拒绝「没有优于基准的模型」。"
            "客户端不能把策略标成已验证。"
        ),
    }


def _latest_completed(
    db: Session,
    *,
    strategy_id: UUID,
    strategy_version_id: UUID,
    kind: ValidationKind,
) -> ValidationRun | None:
    return db.scalars(
        select(ValidationRun)
        .where(
            ValidationRun.strategy_id == strategy_id,
            ValidationRun.strategy_version_id == strategy_version_id,
            ValidationRun.kind == kind,
            ValidationRun.status == ValidationRunStatus.COMPLETED,
        )
        .order_by(ValidationRun.created_at.desc())
    ).first()


def maybe_apply_validated(
    db: Session, *, strategy_id: UUID | None, strategy_version_id: UUID | None
) -> None:
    """System-only VALIDATED transition. Never called from client PATCH."""
    if strategy_id is None or strategy_version_id is None:
        return
    strategy = db.get(Strategy, strategy_id)
    if strategy is None or strategy.status in _LIVE_STATUSES:
        return
    if strategy.status not in {StrategyStatus.BACKTESTED, StrategyStatus.VALIDATED}:
        return

    latest = {
        kind: _latest_completed(
            db,
            strategy_id=strategy_id,
            strategy_version_id=strategy_version_id,
            kind=kind,
        )
        for kind in _VALIDATED_KINDS
    }
    oks = {
        kind: row is not None and row.passed and row.error is None for kind, row in latest.items()
    }
    before = strategy.status.value
    if all(oks.values()):
        if strategy.status != StrategyStatus.VALIDATED:
            strategy.status = StrategyStatus.VALIDATED
            db.add(
                AuditLog(
                    actor="system",
                    action="Strategy Validated",
                    object_type="strategy",
                    object_id=str(strategy.id),
                    before={"status": before},
                    after={
                        "status": StrategyStatus.VALIDATED.value,
                        **{
                            f"{kind.value.lower()}_id": str(row.id)
                            for kind, row in latest.items()
                            if row is not None
                        },
                    },
                )
            )
        return
    if strategy.status == StrategyStatus.VALIDATED:
        strategy.status = StrategyStatus.BACKTESTED
        db.add(
            AuditLog(
                actor="system",
                action="Strategy Validation Revoked",
                object_type="strategy",
                object_id=str(strategy.id),
                before={"status": before},
                after={
                    "status": StrategyStatus.BACKTESTED.value,
                    **{f"{kind.value.lower()}_passed": oks[kind] for kind in _VALIDATED_KINDS},
                },
            )
        )


def _template_backtest(db: Session, version: StrategyVersion, backtest_id: UUID | None) -> Backtest:
    if backtest_id is not None:
        backtest = db.get(Backtest, backtest_id)
        if backtest is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回测不存在")
        if backtest.strategy_version_id != version.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="回测不属于该策略版本，拒绝借用其标的池与快照。",
            )
        if backtest.status != BacktestStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="需要一次已完成的回测作为标的池与快照来源。",
            )
        return backtest
    backtest = db.scalars(
        select(Backtest)
        .where(
            Backtest.strategy_version_id == version.id,
            Backtest.status == BacktestStatus.COMPLETED,
        )
        .order_by(Backtest.created_at.desc())
    ).first()
    if backtest is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="先跑一次全样本回测。验证任务需要同一份标的池与数据快照，不会猜测 SPY。",
        )
    return backtest


def create_validation_run(db: Session, payload: ValidationCreate) -> ValidationRun:
    """Generic validation creation — params validated against spec registry."""
    try:
        # Case-insensitive enum matching
        kind_str = payload.kind.upper()
        kind = ValidationKind[kind_str]
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未知的验证类型：{payload.kind}",
        ) from exc

    spec = get_spec(kind)
    if kind is ValidationKind.DSR:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="DSR 由回测完成时从试验台账自动写入，不接受手动创建。",
        )
    schema = spec.params_schema()
    # Validate params against schema
    try:
        validated_params = schema(**payload.params)
    except Exception as exc:  # pydantic.ValidationError
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    version = get_version(db, payload.strategy_version_id)

    # Pre-backtest strategy validation (e.g., parameter reading checks)
    spec.validate_strategy(db, version, validated_params)

    template = _template_backtest(db, version, payload.backtest_id)

    # For engine kinds, check concurrency
    if kind in _ENGINE_KINDS:
        settings = get_settings()
        if count_inflight_engine_jobs(db) >= settings.max_inflight_backtests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="并发回测已达上限，请等待正在运行的任务完成后再提交验证。",
            )

    # Build params dict from validated model
    try:
        params_dict = spec.prepare_params(db, version, template, validated_params)
    except WalkForwardError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    run = ValidationRun(
        strategy_id=version.strategy_id,
        strategy_version_id=version.id,
        backtest_id=template.id,
        kind=kind,
        status=ValidationRunStatus.QUEUED,
        progress_step="Queued",
        params=params_dict,
        result={},
        passed=False,
    )
    db.add(run)
    db.flush()
    db.add(
        AuditLog(
            actor="local",
            action=f"{spec.display_name} Started",
            object_type="validation_run",
            object_id=str(run.id),
            after={
                "strategy_version_id": str(version.id),
                "kind": kind.value,
                "params": params_dict,
            },
        )
    )
    db.commit()
    db.refresh(run)

    spec.enqueue(str(run.id), params=params_dict)

    db.refresh(run)
    return run


def _spa_seed(template: Backtest, seed: int | None) -> int:
    if seed is not None:
        return int(seed)
    return int(template.id.int % (2**32 - 1))


def load_spa_paths(
    db: Session,
    *,
    family_id: UUID,
    snapshot_id: UUID | None,
) -> list[tuple[str | None, list[dict[str, Any]]]]:
    """In-sample trials for one family + snapshot. OOS fold rows are excluded."""
    query = select(ExperimentTrial).where(
        ExperimentTrial.strategy_family == family_id,
        or_(ExperimentTrial.is_oos.is_(False), ExperimentTrial.is_oos.is_(None)),
        ExperimentTrial.backtest_id.is_not(None),
    )
    if snapshot_id is not None:
        query = query.where(ExperimentTrial.data_snapshot_id == snapshot_id)
    trials = list(db.scalars(query).all())
    snapshots = {row.data_snapshot_id for row in trials}
    if snapshot_id is None and len(snapshots) > 1:
        raise SpaError("试验台账混有不同数据快照，拒绝跨快照做 Reality Check。")
    paths: list[tuple[str | None, list[dict[str, Any]]]] = []
    seen: set[UUID] = set()
    for trial in trials:
        if trial.backtest_id is None or trial.backtest_id in seen:
            continue
        backtest = db.get(Backtest, trial.backtest_id)
        if backtest is None or backtest.status != BacktestStatus.COMPLETED:
            continue
        points = equity_payload(db, backtest.id)
        if len(points) < 2:
            continue
        seen.add(backtest.id)
        paths.append((str(backtest.id), points))
    return paths
