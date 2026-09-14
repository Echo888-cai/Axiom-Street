"""P3.3 validation plan: one typed view of what each gate needs, whether it is
applicable for this strategy/backtest, how much it costs, and which out-of-sample
window is frozen.

Applicability is derived from facts, never optimism:

- ``insufficient_samples`` — the reference equity has fewer trading days than the
  gate needs (Bootstrap 252, Regime 60 per axis, Walk-Forward train+test years).
- ``parameter_not_read`` — a scan would perturb a parameter the strategy code
  never reads (``GetParameter("...")``), so an "equal curve" must not pass.
- ``insufficient_trials`` — SPA needs ≥2 distinguishable trials in the ledger.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.models import (
    Backtest,
    BacktestEquity,
    BacktestStatus,
    ExperimentTrial,
    Strategy,
    StrategyVersion,
)
from services.api.services import backtests as backtest_service
from services.api.services import strategies as strategy_service
from services.api.services.validation_spec import all_specs

# 每类闸门的最小样本/参数要求（与执行器口径保持一致）。
BOOTSTRAP_MIN_OBS = 252
REGIME_MIN_AXIS_OBS = 60
WF_TRAIN_YEARS = 3
WF_TEST_YEARS = 1

# 扫描类闸门的扰动轴与对应的 LEAN 运行数参数键。
SCAN_AXES: dict[str, tuple[str, str]] = {
    "PBO": ("parameter_key", "values"),
    "SENSITIVITY": ("parameter_key", "values"),
    "COST": ("slippage_parameter", "costs_bps"),
}

# 每类闸门的单次 LEAN 运行经验耗时（分钟），仅用于资源估计，不是承诺。
LEAN_MINUTES_PER_RUN = 3.0


def _reference_backtest(
    db: Session, strategy_version_id: UUID, backtest_id: UUID | None
) -> Backtest | None:
    if backtest_id is not None:
        return db.get(Backtest, backtest_id)
    return db.scalars(
        select(Backtest)
        .where(
            Backtest.strategy_version_id == strategy_version_id,
            Backtest.status == BacktestStatus.COMPLETED,
        )
        .order_by(Backtest.finished_at.desc().nullslast())
        .limit(1)
    ).first()


def _trading_days(db: Session, backtest: Backtest | None) -> int:
    if backtest is None:
        return 0
    return int(
        db.scalar(
            select(func.count())
            .select_from(BacktestEquity)
            .where(BacktestEquity.backtest_id == backtest.id)
        )
        or 0
    )


def _parameter_is_read(code: str, key: str) -> bool:
    return f'GetParameter("{key}")' in code or f"GetParameter('{key}')" in code


def _scan_estimate(kind: str, params: dict[str, Any]) -> int:
    if kind == "COST":
        costs = params.get("costs_bps") or []
        return max(len(costs), 1)
    values = params.get("values") or []
    return max(len(values), 1)


def build_validation_plan(
    db: Session,
    *,
    strategy_version_id: UUID,
    backtest_id: UUID | None = None,
) -> dict[str, Any]:
    version = db.get(StrategyVersion, strategy_version_id)
    if version is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="策略版本不存在")
    strategy = db.get(Strategy, version.strategy_id)
    reference = _reference_backtest(db, strategy_version_id, backtest_id)
    days = _trading_days(db, reference)
    code = version.code or ""
    family_id = strategy.family_id or strategy.id if strategy else version.strategy_id
    trials = int(
        db.scalar(
            select(func.count())
            .select_from(ExperimentTrial)
            .where(ExperimentTrial.strategy_family == family_id)
        )
        or 0
    )

    gates: list[dict[str, Any]] = []
    for spec in all_specs():
        kind = spec.kind.value
        params = dict(spec.params_schema()().model_dump()) if spec.params_schema() else {}
        supported_operators: list[str] = []
        applicable = True
        reason_code = "ok"
        reason = "条件满足，可直接运行。"
        lean_runs = 0

        if kind in SCAN_AXES:
            axis_key, values_key = SCAN_AXES[kind]
            parameter_key = str(params.get(axis_key) or params.get("parameter_key") or "lookback")
            supported_operators = [parameter_key]
            if reference is None or reference.status != BacktestStatus.COMPLETED:
                applicable, reason_code = False, "missing_reference_backtest"
                reason = "扫描需要一次已完成回测作为参考。"
            elif not _parameter_is_read(code, parameter_key):
                applicable, reason_code = False, "parameter_not_read"
                reason = (
                    f"策略代码没有读取参数 {parameter_key}（GetParameter），"
                    "扫描只会得到等同曲线，不算通过。"
                )
            else:
                lean_runs = _scan_estimate(kind, params)
        elif kind == "WALK_FORWARD":
            required = (WF_TRAIN_YEARS + WF_TEST_YEARS) * 252
            if days < required:
                applicable, reason_code = False, "insufficient_samples"
                reason = f"Walk-Forward 需要约 {required} 个交易日（训练+测试），当前 {days}。"
            else:
                lean_runs = max(days // (WF_TEST_YEARS * 252), 1)
        elif kind == "BOOTSTRAP":
            if days < BOOTSTRAP_MIN_OBS:
                applicable, reason_code = False, "insufficient_samples"
                reason = f"Bootstrap 需要 ≥{BOOTSTRAP_MIN_OBS} 个交易日，当前 {days}。"
        elif kind == "REGIME":
            if days < REGIME_MIN_AXIS_OBS:
                applicable, reason_code = False, "insufficient_samples"
                reason = f"制度切片每条轴需要 ≥{REGIME_MIN_AXIS_OBS} 个交易日，当前 {days}。"
        elif kind == "SPA":
            if trials < 2:
                applicable, reason_code = False, "insufficient_trials"
                reason = f"SPA 需要 ≥2 条可区分试验，当前台账 {trials} 条。"
        elif kind == "DSR":
            if trials == 0:
                reason = "台账暂无试验：DSR 只做范围核验，重跑后获得代次绑定。"
        elif reference is None:
            applicable, reason_code = False, "missing_reference_backtest"
            reason = "该检验需要一次已完成回测。"

        gates.append(
            {
                "kind": kind,
                "display_name": spec.display_name,
                "auto_on_backtest": spec.auto_on_backtest,
                "applicable": applicable,
                "reason_code": reason_code,
                "reason": reason,
                "supported_operators": supported_operators,
                "estimate": {
                    "lean_runs": lean_runs,
                    "est_minutes": round(lean_runs * LEAN_MINUTES_PER_RUN, 1),
                },
            }
        )

    applicable_gates = [g for g in gates if g["applicable"]]
    return {
        "strategy_version_id": str(strategy_version_id),
        "reference_backtest_id": str(reference.id) if reference else None,
        "trading_days": days,
        "trial_count": trials,
        "frozen": {
            "start": reference.start_date.isoformat() if reference else None,
            "end": reference.end_date.isoformat() if reference else None,
            "note": "样本外区间与验证范围取自参考回测，运行前冻结，之后不随新数据漂移。",
        },
        "gates": gates,
        "totals": {
            "gates_total": len(gates),
            "gates_applicable": len(applicable_gates),
            "lean_runs": sum(g["estimate"]["lean_runs"] for g in applicable_gates),
            "est_minutes": round(sum(g["estimate"]["est_minutes"] for g in applicable_gates), 1),
        },
    }


def latest_reference(db: Session, strategy_id: UUID) -> Backtest | None:
    """Convenience for callers that only have a strategy id."""
    version = strategy_service.latest_version(db, strategy_id)
    if version is None:
        return None
    return (
        backtest_service.latest_completed(db, version.id)
        if hasattr(backtest_service, "latest_completed")
        else _reference_backtest(db, version.id, None)
    )
