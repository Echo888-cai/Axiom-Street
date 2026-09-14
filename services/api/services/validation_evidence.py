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
        passed[kind] = not reason
        if reason:
            reasons[kind.value] = reason
    return ValidationEvidence(latest, passed, reasons, anchor.id if anchor else None)
