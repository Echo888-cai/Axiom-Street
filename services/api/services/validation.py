"""Phase 3 validation runs. DSR, walk-forward, PBO, sensitivity, and cost gate VALIDATED."""

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
from quant.metrics.pbo import (
    LOOKBACK_PARAMETER,
    strategy_reads_lookback,
    strategy_reads_parameter,
)
from quant.validation.cost import (
    DEFAULT_COSTS_BPS,
    DEFAULT_REALISTIC_BPS,
    FEE_PARAMETER,
    SLIPPAGE_PARAMETER,
)
from quant.validation.cost import MAX_GRID as COST_MAX_GRID
from quant.validation.cost import MIN_GRID as COST_MIN_GRID
from quant.validation.sensitivity import DEFAULT_LOOKBACK_GRID
from quant.validation.sensitivity import MAX_GRID as SENS_MAX_GRID
from quant.validation.sensitivity import MIN_GRID as SENS_MIN_GRID
from quant.validation.walk_forward import WalkForwardError, WalkForwardSpec, build_folds
from services.api.models import (
    AuditLog,
    Backtest,
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
from services.api.schemas import (
    CostScanCreate,
    PBOScanCreate,
    SensitivityCreate,
    ValidationRunOut,
    WalkForwardCreate,
)
from services.api.services.strategies import get_version
from services.api.settings import get_settings

_BT_INFLIGHT = {BacktestStatus.QUEUED, BacktestStatus.STARTING, BacktestStatus.RUNNING}
_WF_INFLIGHT = {ValidationRunStatus.QUEUED, ValidationRunStatus.RUNNING}
_ENGINE_KINDS = (
    ValidationKind.WALK_FORWARD,
    ValidationKind.PBO,
    ValidationKind.SENSITIVITY,
    ValidationKind.COST,
)
_VALIDATED_KINDS = (
    ValidationKind.WALK_FORWARD,
    ValidationKind.DSR,
    ValidationKind.PBO,
    ValidationKind.SENSITIVITY,
    ValidationKind.COST,
)
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


def count_inflight_engine_jobs(db: Session) -> int:
    backtests = int(
        db.scalar(select(func.count()).select_from(Backtest).where(Backtest.status.in_(_BT_INFLIGHT)))
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
        "validated_requires": [kind.value for kind in _VALIDATED_KINDS],
        "available": [kind.value for kind in _VALIDATED_KINDS],
        "missing": ["BOOTSTRAP", "REGIME"],
        "note": (
            "VALIDATED 由系统持有：Walk-forward 通过、同版本 DSR 过 95% 线、"
            "参数扫描 PBO ≤ 0.5、敏感性为高原而非孤峰、且临界单边成本高于真实成本。"
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


def _template_backtest(
    db: Session, version: StrategyVersion, backtest_id: UUID | None
) -> Backtest:
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


def _enqueue_walk_forward(run_id: str, *, n_folds: int) -> None:
    settings = get_settings()
    if settings.sync_backtests:
        from services.worker.tasks import execute_walk_forward

        execute_walk_forward(run_id)
        return
    from services.worker.tasks import run_walk_forward_task

    timeout = (settings.lean_timeout_seconds + 60) * max(n_folds, 1) + 120
    run_walk_forward_task.apply_async(
        args=[run_id],
        time_limit=timeout,
        soft_time_limit=max(timeout - 60, 60),
    )


def create_walk_forward_run(db: Session, payload: WalkForwardCreate) -> ValidationRun:
    version = get_version(db, payload.strategy_version_id)
    template = _template_backtest(db, version, payload.backtest_id)
    start = payload.start_date or template.start_date
    end = payload.end_date or template.end_date
    mode = payload.mode.strip().lower()
    try:
        folds = build_folds(
            WalkForwardSpec(
                start=start,
                end=end,
                train_years=payload.train_years,
                test_years=payload.test_years,
                mode=mode,
                embargo_days=payload.embargo_days,
            )
        )
    except WalkForwardError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    settings = get_settings()
    if count_inflight_engine_jobs(db) >= settings.max_inflight_backtests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="并发回测已达上限，请等待正在运行的任务完成后再提交 Walk-forward。",
        )

    run = ValidationRun(
        strategy_id=version.strategy_id,
        strategy_version_id=version.id,
        backtest_id=template.id,
        kind=ValidationKind.WALK_FORWARD,
        status=ValidationRunStatus.QUEUED,
        progress_step="Queued",
        params={
            "mode": mode,
            "train_years": payload.train_years,
            "test_years": payload.test_years,
            "embargo_days": payload.embargo_days,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "benchmark": template.benchmark,
            "initial_capital": template.initial_capital,
            "data_snapshot_id": str(template.data_snapshot_id)
            if template.data_snapshot_id
            else None,
            "universe_snapshot": template.universe_snapshot or [],
            "parameters": template.parameters or {},
            "folds": [fold.to_dict() for fold in folds],
        },
        result={},
        passed=False,
    )
    db.add(run)
    db.flush()
    db.add(
        AuditLog(
            actor="local",
            action="Walk-Forward Started",
            object_type="validation_run",
            object_id=str(run.id),
            after={
                "strategy_version_id": str(version.id),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "mode": mode,
                "n_folds": len(folds),
            },
        )
    )
    db.commit()
    db.refresh(run)
    _enqueue_walk_forward(str(run.id), n_folds=len(folds))
    db.refresh(run)
    return run


def _enqueue_pbo_scan(run_id: str, *, n_values: int) -> None:
    settings = get_settings()
    if settings.sync_backtests:
        from services.worker.tasks import execute_pbo_scan

        execute_pbo_scan(run_id)
        return
    from services.worker.tasks import run_pbo_scan_task

    timeout = (settings.lean_timeout_seconds + 60) * max(n_values, 1) + 120
    run_pbo_scan_task.apply_async(
        args=[run_id],
        time_limit=timeout,
        soft_time_limit=max(timeout - 60, 60),
    )


def create_pbo_scan(db: Session, payload: PBOScanCreate) -> ValidationRun:
    version = get_version(db, payload.strategy_version_id)
    if not strategy_reads_lookback(version.code):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "该版本没有读取 LEAN 参数 lookback（GetParameter(\"lookback\")）。"
                "扫一个策略读不到的字段会得到相同净值，PBO 没有意义。请先提交新版本。"
            ),
        )
    if payload.parameter_key != LOOKBACK_PARAMETER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="目前只支持扫描 LEAN 参数 lookback，不要扫策略读不到的字段。",
        )
    values = sorted({int(v) for v in payload.values})
    if len(values) < 2 or len(values) > 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="参数扫描需要 2–12 个互异正整数。",
        )
    if any(v < 2 for v in values):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lookback 必须 >= 2",
        )
    template = _template_backtest(db, version, payload.backtest_id)
    start = payload.start_date or template.start_date
    end = payload.end_date or template.end_date
    if end <= start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="结束日期必须晚于开始日期")

    settings = get_settings()
    if count_inflight_engine_jobs(db) >= settings.max_inflight_backtests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="并发回测已达上限，请等待正在运行的任务完成后再提交参数扫描。",
        )

    run = ValidationRun(
        strategy_id=version.strategy_id,
        strategy_version_id=version.id,
        backtest_id=template.id,
        kind=ValidationKind.PBO,
        status=ValidationRunStatus.QUEUED,
        progress_step="Queued",
        params={
            "parameter_key": LOOKBACK_PARAMETER,
            "values": values,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "benchmark": template.benchmark,
            "initial_capital": template.initial_capital,
            "data_snapshot_id": str(template.data_snapshot_id)
            if template.data_snapshot_id
            else None,
            "universe_snapshot": template.universe_snapshot or [],
            "base_parameters": template.parameters or {},
        },
        result={},
        passed=False,
    )
    db.add(run)
    db.flush()
    db.add(
        AuditLog(
            actor="local",
            action="PBO Scan Started",
            object_type="validation_run",
            object_id=str(run.id),
            after={"values": values, "n_values": len(values)},
        )
    )
    db.commit()
    db.refresh(run)
    _enqueue_pbo_scan(str(run.id), n_values=len(values))
    db.refresh(run)
    return run


def _enqueue_sensitivity_scan(run_id: str, *, n_values: int) -> None:
    settings = get_settings()
    if settings.sync_backtests:
        from services.worker.tasks import execute_sensitivity_scan

        execute_sensitivity_scan(run_id)
        return
    from services.worker.tasks import run_sensitivity_scan_task

    timeout = (settings.lean_timeout_seconds + 60) * max(n_values, 1) + 120
    run_sensitivity_scan_task.apply_async(
        args=[run_id],
        time_limit=timeout,
        soft_time_limit=max(timeout - 60, 60),
    )


def create_sensitivity_scan(db: Session, payload: SensitivityCreate) -> ValidationRun:
    version = get_version(db, payload.strategy_version_id)
    if payload.parameter_key != LOOKBACK_PARAMETER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="目前只支持扰动 LEAN 参数 lookback，不要扫策略读不到的字段。",
        )
    if not strategy_reads_parameter(version.code, LOOKBACK_PARAMETER):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "该版本没有读取 LEAN 参数 lookback（GetParameter(\"lookback\")）。"
                "扰动一个策略读不到的字段会得到相同净值，敏感性没有意义。请先提交新版本。"
            ),
        )
    values = sorted({int(v) for v in (payload.values or list(DEFAULT_LOOKBACK_GRID))})
    if len(values) < SENS_MIN_GRID or len(values) > SENS_MAX_GRID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"敏感性网格需要 {SENS_MIN_GRID}–{SENS_MAX_GRID} 个互异正整数。",
        )
    if any(v < 2 for v in values):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lookback 必须 >= 2",
        )
    template = _template_backtest(db, version, payload.backtest_id)
    start = payload.start_date or template.start_date
    end = payload.end_date or template.end_date
    if end <= start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="结束日期必须晚于开始日期")

    settings = get_settings()
    if count_inflight_engine_jobs(db) >= settings.max_inflight_backtests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="并发回测已达上限，请等待正在运行的任务完成后再提交敏感性扫描。",
        )

    run = ValidationRun(
        strategy_id=version.strategy_id,
        strategy_version_id=version.id,
        backtest_id=template.id,
        kind=ValidationKind.SENSITIVITY,
        status=ValidationRunStatus.QUEUED,
        progress_step="Queued",
        params={
            "parameter_key": LOOKBACK_PARAMETER,
            "values": values,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "benchmark": template.benchmark,
            "initial_capital": template.initial_capital,
            "data_snapshot_id": str(template.data_snapshot_id)
            if template.data_snapshot_id
            else None,
            "universe_snapshot": template.universe_snapshot or [],
            "base_parameters": template.parameters or {},
        },
        result={},
        passed=False,
    )
    db.add(run)
    db.flush()
    db.add(
        AuditLog(
            actor="local",
            action="Sensitivity Scan Started",
            object_type="validation_run",
            object_id=str(run.id),
            after={"values": values, "n_values": len(values)},
        )
    )
    db.commit()
    db.refresh(run)
    _enqueue_sensitivity_scan(str(run.id), n_values=len(values))
    db.refresh(run)
    return run


def _enqueue_cost_scan(run_id: str, *, n_values: int) -> None:
    settings = get_settings()
    if settings.sync_backtests:
        from services.worker.tasks import execute_cost_scan

        execute_cost_scan(run_id)
        return
    from services.worker.tasks import run_cost_scan_task

    timeout = (settings.lean_timeout_seconds + 60) * max(n_values, 1) + 120
    run_cost_scan_task.apply_async(
        args=[run_id],
        time_limit=timeout,
        soft_time_limit=max(timeout - 60, 60),
    )


def create_cost_scan(db: Session, payload: CostScanCreate) -> ValidationRun:
    version = get_version(db, payload.strategy_version_id)
    if not strategy_reads_parameter(version.code, SLIPPAGE_PARAMETER):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"该版本没有读取 LEAN 参数 {SLIPPAGE_PARAMETER}（GetParameter(\"{SLIPPAGE_PARAMETER}\")）。"
                "成本扫描必须能改滑点，否则净值不变。请先提交新版本。"
            ),
        )
    raw_costs = payload.costs_bps if payload.costs_bps else list(DEFAULT_COSTS_BPS)
    costs: list[float] = []
    seen: set[float] = set()
    for item in raw_costs:
        value = float(item)
        if value != value or value < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="成本必须是 ≥ 0 的有限数，单位 bps。",
            )
        if value in seen:
            continue
        seen.add(value)
        costs.append(value)
    costs.sort()
    if len(costs) < COST_MIN_GRID or len(costs) > COST_MAX_GRID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"成本网格需要 {COST_MIN_GRID}–{COST_MAX_GRID} 个互异非负 bps。",
        )
    if 0.0 not in costs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="成本网格必须包含 0 bps，否则无法判断临界成本是否被低估。",
        )
    realistic = float(
        payload.realistic_one_way_bps
        if payload.realistic_one_way_bps is not None
        else DEFAULT_REALISTIC_BPS
    )
    if realistic != realistic or realistic < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="真实单边成本必须是 ≥ 0 的有限数。",
        )
    template = _template_backtest(db, version, payload.backtest_id)
    start = payload.start_date or template.start_date
    end = payload.end_date or template.end_date
    if end <= start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="结束日期必须晚于开始日期")

    settings = get_settings()
    if count_inflight_engine_jobs(db) >= settings.max_inflight_backtests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="并发回测已达上限，请等待正在运行的任务完成后再提交成本扫描。",
        )

    run = ValidationRun(
        strategy_id=version.strategy_id,
        strategy_version_id=version.id,
        backtest_id=template.id,
        kind=ValidationKind.COST,
        status=ValidationRunStatus.QUEUED,
        progress_step="Queued",
        params={
            "costs_bps": costs,
            "realistic_one_way_bps": realistic,
            "slippage_parameter": SLIPPAGE_PARAMETER,
            "fee_parameter": FEE_PARAMETER,
            "fee_usd": 0.0,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "benchmark": template.benchmark,
            "initial_capital": template.initial_capital,
            "data_snapshot_id": str(template.data_snapshot_id)
            if template.data_snapshot_id
            else None,
            "universe_snapshot": template.universe_snapshot or [],
            "base_parameters": template.parameters or {},
        },
        result={},
        passed=False,
    )
    db.add(run)
    db.flush()
    db.add(
        AuditLog(
            actor="local",
            action="Cost Scan Started",
            object_type="validation_run",
            object_id=str(run.id),
            after={"costs_bps": costs, "realistic_one_way_bps": realistic},
        )
    )
    db.commit()
    db.refresh(run)
    _enqueue_cost_scan(str(run.id), n_values=len(costs))
    db.refresh(run)
    return run
