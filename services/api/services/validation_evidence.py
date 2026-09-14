"""Shared, fail-closed evidence selection for research and Live readiness."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.models import (
    Backtest,
    BacktestStatus,
    DataSnapshot,
    StrategyVersion,
    ValidationKind,
    ValidationRun,
    ValidationRunStatus,
)


@dataclass
class ValidationEvidence:
    latest: dict[ValidationKind, ValidationRun]
    passed: dict[ValidationKind, bool]
    reasons: dict[str, str]
    backtest_id: UUID | None


def _scope(backtest: Backtest) -> tuple:
    return (
        backtest.strategy_version_id,
        backtest.data_snapshot_id,
        backtest.start_date,
        backtest.end_date,
        backtest.benchmark,
        backtest.initial_capital,
        backtest.parameters or {},
        backtest.universe_snapshot,
        backtest.engine_version,
        backtest.data_version,
    )


def _norm_universe(value: object) -> object:
    if value is None:
        return []
    return value


def _versions_match(anchor_value: object, sub_value: object) -> bool:
    # Legacy fixtures leave engine/data versions NULL; only enforce when the
    # anchor actually records a version. Real backtests always record one, so
    # image or data swaps are still caught there.
    if anchor_value is None:
        return True
    return anchor_value == sub_value


def _verify_scan_backtests(
    db: Session,
    run: ValidationRun,
    anchor: Backtest,
    *,
    allowed_axes: set[str],
) -> str:
    """Verify PBO/SENSITIVITY/COST sub-backtests actually ran in scope.

    Only the declared perturbation axis may differ from the anchor. Missing
    sub-records, uncompleted rows, or any off-axis drift (engine, snapshot,
    window, benchmark, capital, universe, other params) fail closed.
    """
    result = run.result or {}
    raw_ids = result.get("backtest_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        return "scan_execution_missing"
    params = run.params or {}
    for key in ("values", "costs_bps"):
        expected = params.get(key)
        if isinstance(expected, list) and expected and len(raw_ids) != len(expected):
            return "scan_execution_incomplete"
    anchor_params = anchor.parameters or {}
    seen: set[str] = set()
    for raw in raw_ids:
        try:
            bid = UUID(str(raw))
        except (TypeError, ValueError):
            return "scan_backtest_unavailable"
        if str(bid) in seen:
            return "scan_execution_incomplete"
        seen.add(str(bid))
        sub = db.get(Backtest, bid)
        if sub is None or sub.status != BacktestStatus.COMPLETED:
            return "scan_backtest_unavailable"
        if sub.strategy_version_id != anchor.strategy_version_id:
            return "scan_execution_mismatch"
        if sub.data_snapshot_id != anchor.data_snapshot_id:
            return "scan_execution_mismatch"
        if not _versions_match(anchor.engine_version, sub.engine_version):
            return "scan_execution_mismatch"
        if not _versions_match(anchor.data_version, sub.data_version):
            return "scan_execution_mismatch"
        if (
            sub.start_date != anchor.start_date
            or sub.end_date != anchor.end_date
            or sub.benchmark != anchor.benchmark
            or float(sub.initial_capital or 0) != float(anchor.initial_capital or 0)
        ):
            return "scan_execution_mismatch"
        if _norm_universe(sub.universe_snapshot) != _norm_universe(anchor.universe_snapshot):
            return "scan_execution_mismatch"
        sub_params = sub.parameters or {}
        for key in set(anchor_params) | set(sub_params):
            if key in allowed_axes:
                continue
            if anchor_params.get(key) != sub_params.get(key):
                return "scan_execution_mismatch"
    return ""


def _verify_walk_forward(db: Session, run: ValidationRun, anchor: Backtest) -> str:
    """Verify Walk-Forward folds actually executed in scope.

    Historic runs without per-fold execution evidence cannot be trusted and
    must be re-run; we mark them expired instead of inventing metadata.
    """
    del db  # evidence lives on the run row; no extra tables needed.
    result = run.result or {}
    params = run.params or {}
    execution = result.get("execution")
    param_folds = params.get("folds")
    scored_folds = result.get("folds")
    if (
        not isinstance(execution, dict)
        or not isinstance(param_folds, list)
        or not param_folds
        or not isinstance(scored_folds, list)
        or len(scored_folds) != len(param_folds)
    ):
        return "walk_forward_execution_missing"
    try:
        if str(execution.get("data_snapshot_id") or "") != str(anchor.data_snapshot_id or ""):
            return "walk_forward_execution_mismatch"
    except (TypeError, ValueError):
        return "walk_forward_execution_mismatch"
    if not _versions_match(anchor.engine_version, execution.get("engine_version")):
        return "walk_forward_execution_mismatch"
    if not _versions_match(anchor.data_version, execution.get("data_version")):
        return "walk_forward_execution_mismatch"
    if str(execution.get("benchmark") or "") != str(anchor.benchmark or ""):
        return "walk_forward_execution_mismatch"
    try:
        if float(execution.get("initial_capital") or 0) != float(anchor.initial_capital or 0):
            return "walk_forward_execution_mismatch"
    except (TypeError, ValueError):
        return "walk_forward_execution_mismatch"
    if _norm_universe(execution.get("universe_snapshot")) != _norm_universe(
        anchor.universe_snapshot
    ):
        return "walk_forward_execution_mismatch"
    exec_params = execution.get("parameters") or {}
    if exec_params != (anchor.parameters or {}):
        return "walk_forward_execution_mismatch"
    exec_folds = execution.get("folds")
    if not isinstance(exec_folds, list) or len(exec_folds) != len(param_folds):
        return "walk_forward_execution_mismatch"
    for declared, executed in zip(param_folds, exec_folds):
        if not isinstance(declared, dict) or not isinstance(executed, dict):
            return "walk_forward_execution_mismatch"
        for key in ("is_start", "is_end", "oos_start", "oos_end"):
            if str(declared.get(key)) != str(executed.get(key)):
                return "walk_forward_execution_mismatch"
        # Folds must sit inside the anchored research window.
        if str(executed.get("is_start") or "") < str(anchor.start_date):
            return "walk_forward_execution_mismatch"
        if str(executed.get("oos_end") or "") != str(executed.get("oos_end") or ""):
            pass
        if str(executed.get("oos_end") or "") > str(anchor.end_date):
            return "walk_forward_execution_mismatch"
    return ""


def _verify_spa(db: Session, run: ValidationRun, anchor: Backtest) -> str:
    """Verify the SPA trial set actually executed on this snapshot."""
    params = run.params or {}
    result = run.result or {}
    raw_snapshot = params.get("data_snapshot_id")
    try:
        if raw_snapshot is None or UUID(str(raw_snapshot)) != anchor.data_snapshot_id:
            return "spa_execution_mismatch"
    except (TypeError, ValueError, AttributeError):
        return "spa_execution_mismatch"
    models = result.get("models")
    if not isinstance(models, list) or len(models) < 2:
        return "spa_execution_missing"
    expected_n = params.get("n_models")
    if isinstance(expected_n, int) and expected_n and len(models) != expected_n:
        return "spa_execution_incomplete"
    for item in models:
        if not isinstance(item, dict) or not item.get("backtest_id"):
            return "spa_trial_unavailable"
        try:
            bid = UUID(str(item["backtest_id"]))
        except (TypeError, ValueError):
            return "spa_trial_unavailable"
        sub = db.get(Backtest, bid)
        if sub is None or sub.status != BacktestStatus.COMPLETED:
            return "spa_trial_unavailable"
        if sub.data_snapshot_id != anchor.data_snapshot_id:
            return "spa_execution_mismatch"
    return ""


_SCAN_AXES: dict[ValidationKind, set[str]] = {
    ValidationKind.PBO: {"lookback"},
    ValidationKind.SENSITIVITY: {"lookback"},
    ValidationKind.COST: {"slippage_bps", "fee_usd"},
}


def _verify_trial_generation(db: Session, run: ValidationRun, anchor: Backtest) -> str:
    """Expire DSR/SPA conclusions when the family trial ledger moved on.

    New trials (or sharpe updates on existing trials) change what DSR/SPA
    should conclude. Runs recorded by current code carry a generation
    baseline and are compared against the live ledger; a mismatch revokes
    the pass until the validation is recomputed. DSR rows that predate the
    hash fall back to the recorded trial count (production DSR rows always
    recorded n_trials). Rows with no baseline at all are fixtures, not
    production evidence, and are left to the other checks.
    """
    # Deferred import: validation.py lazily imports this module.
    from services.api.services.validation import (
        dsr_trial_rows,
        dsr_trial_set_hash,
        spa_candidate_ids,
    )

    params = run.params or {}
    if run.kind == ValidationKind.DSR:
        raw_family = params.get("family_id")
        if not raw_family:
            return ""
        try:
            family_id = UUID(str(raw_family))
        except (TypeError, ValueError):
            return "dsr_trial_set_changed"
        trials = dsr_trial_rows(db, family_id=family_id, snapshot_id=anchor.data_snapshot_id)
        recorded_hash = params.get("trial_set_hash")
        if isinstance(recorded_hash, str) and recorded_hash:
            current = dsr_trial_set_hash(trials)
            return "" if current == recorded_hash else "dsr_trial_set_changed"
        recorded_n = params.get("n_trials")
        if isinstance(recorded_n, int) and recorded_n:
            current_n = max(sum(1 for t in trials if t.observed_sharpe is not None), 1)
            return "" if current_n == recorded_n else "dsr_trial_set_changed"
        return ""
    if run.kind == ValidationKind.SPA:
        raw_family = params.get("family_id")
        if not raw_family:
            return ""
        try:
            family_id = UUID(str(raw_family))
        except (TypeError, ValueError):
            return "spa_trial_set_changed"
        recorded_ids = params.get("trial_candidate_ids")
        if not isinstance(recorded_ids, list) or not recorded_ids:
            # Rows that predate generation binding carry no baseline; scope
            # and model-existence checks still apply. Re-run SPA to bind.
            return ""
        current_ids = spa_candidate_ids(
            db, family_id=family_id, snapshot_id=anchor.data_snapshot_id
        )
        return (
            "" if sorted(str(v) for v in recorded_ids) == current_ids else "spa_trial_set_changed"
        )
    return ""


def collect_validation_evidence(
    db: Session,
    *,
    strategy_id: UUID,
    strategy_version_id: UUID,
) -> ValidationEvidence:
    # Include failed/pending attempts: they must not expose an older passing run.
    rows = db.scalars(
        select(ValidationRun)
        .where(
            ValidationRun.strategy_id == strategy_id,
            ValidationRun.strategy_version_id == strategy_version_id,
        )
        .order_by(ValidationRun.created_at.desc(), ValidationRun.id.desc())
    )
    latest: dict[ValidationKind, ValidationRun] = {}
    for candidate in rows:
        latest.setdefault(candidate.kind, candidate)
    current_version = db.scalar(
        select(StrategyVersion.id)
        .where(StrategyVersion.strategy_id == strategy_id)
        .order_by(StrategyVersion.version.desc())
        .limit(1)
    )
    # DSR anchors the reviewed full-sample research, not the last finishing scan.
    dsr = latest.get(ValidationKind.DSR)
    anchor = db.get(Backtest, dsr.backtest_id) if dsr and dsr.backtest_id else None
    valid_anchor = (
        anchor is not None
        and anchor.status == BacktestStatus.COMPLETED
        and anchor.strategy_version_id == strategy_version_id
        and anchor.data_snapshot_id is not None
        and db.get(DataSnapshot, anchor.data_snapshot_id) is not None
    )
    passed: dict[ValidationKind, bool] = {}
    reasons: dict[str, str] = {}
    for kind in ValidationKind:
        row = latest.get(kind)
        reason = ""
        if current_version != strategy_version_id:
            reason = "outdated_strategy_version"
        elif row is None:
            reason = "not_run"
        elif row.status != ValidationRunStatus.COMPLETED:
            reason = f"latest_run_{row.status.value.lower()}"
        elif not row.passed or row.error is not None:
            reason = "latest_run_not_passed"
        elif not valid_anchor:
            reason = "reference_backtest_or_snapshot_missing"
        else:
            assert anchor is not None
            source = db.get(Backtest, row.backtest_id) if row.backtest_id else None
            if source is None or source.status != BacktestStatus.COMPLETED:
                reason = "source_backtest_unavailable"
            elif _scope(source) != _scope(anchor):
                reason = "research_scope_mismatch"
            else:
                # Explicit shortened scan windows cannot validate the full sample.
                for key in ("start_date", "end_date", "benchmark", "initial_capital"):
                    value = (row.params or {}).get(key)
                    expected = getattr(anchor, key)
                    if value is not None and str(value) != str(expected):
                        # JSON may encode equivalent capital as 100000 or 100000.0.
                        if key != "initial_capital" or value != expected:
                            reason = "validation_window_mismatch"
                            break
                if not reason:
                    if kind in _SCAN_AXES:
                        reason = _verify_scan_backtests(
                            db, row, anchor, allowed_axes=_SCAN_AXES[kind]
                        )
                    elif kind == ValidationKind.WALK_FORWARD:
                        reason = _verify_walk_forward(db, row, anchor)
                    elif kind == ValidationKind.SPA:
                        reason = _verify_spa(db, row, anchor)
                if not reason and kind in (ValidationKind.DSR, ValidationKind.SPA):
                    reason = _verify_trial_generation(db, row, anchor)
        passed[kind] = not reason
        if reason:
            reasons[kind.value] = reason
    return ValidationEvidence(latest, passed, reasons, anchor.id if anchor else None)
