"""Deterministic suggestion derivation for the copilot right-rail (P5-3).

Pure read-only layer that turns the trial ledger, gate runs and validation
registry into actionable, executable cards. It is the *source of truth* for
what can be run: every ``run_validation`` card carries a payload that the
existing ``POST /validation`` channel accepts unchanged. When the model
provider is enabled, the LLM only picks among these cards — it can never invent
an action.

Placement note: this module deliberately sits OUTSIDE the copilot package so
it may read ``StrategyVersion.code`` (to test whether a strategy reads the LEAN
parameter a sweep needs) — a read forbidden inside the scanned copilot
sources. Nothing here writes to the DB or crosses the outbound boundary: cards
carry kind / version / backtest ids and spec-default parameter grids only,
never strategy source, parameter config, or price series.

Read-only is enforced by ``tests/unit/test_copilot_isolation.py``
(``test_suggestions_module_*``): no ORM write calls, no write-path service
imports, and card output keys are white-listed against future source leakage.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant.metrics.pbo import strategy_reads_lookback, strategy_reads_parameter
from quant.validation.cost import DEFAULT_COSTS_BPS, SLIPPAGE_PARAMETER
from quant.validation.sensitivity import DEFAULT_LOOKBACK_GRID
from services.api.models import (
    Backtest,
    BacktestStatus,
    DataSnapshot,
    ExperimentTrial,
    Strategy,
    StrategyStatus,
    StrategyVersion,
    ValidationKind,
    ValidationRun,
    ValidationRunStatus,
)

#: Every key a suggestion card may carry. The isolation test asserts the
#: derivation never emits a field outside this set, so research IP cannot leak
#: into a card by accident.
CARD_KEYS: frozenset[str] = frozenset(
    {
        "key",
        "action",
        "executable",
        "validation_kind",
        "strategy_version_id",
        "target_version",
        "template_backtest_id",
        "params",
        "reason_code",
    }
)

ACTION_RUN_VALIDATION = "run_validation"
ACTION_GUIDE = "guide"
ACTION_DISCIPLINE = "discipline"

# DSR is auto-written from the trial ledger on backtest completion and manual
# creation is rejected by the server (409) — never suggest it.
_SUGGESTIBLE_KINDS: tuple[ValidationKind, ...] = (
    ValidationKind.WALK_FORWARD,
    ValidationKind.PBO,
    ValidationKind.SENSITIVITY,
    ValidationKind.COST,
    ValidationKind.BOOTSTRAP,
    ValidationKind.REGIME,
    ValidationKind.SPA,
)

_INFLIGHT_STATUSES = (ValidationRunStatus.QUEUED, ValidationRunStatus.RUNNING)


def _kind_params(kind: ValidationKind) -> dict[str, Any]:
    """Minimal params that pass schema + validate_strategy with spec defaults.

    Grid kinds must carry an explicit grid (PBO rejects an empty values list;
    the worker reads the persisted grid for the other kinds too). Scalars rely
    on the spec's own model defaults.
    """
    if kind in (ValidationKind.PBO, ValidationKind.SENSITIVITY):
        return {"values": list(DEFAULT_LOOKBACK_GRID)}
    if kind == ValidationKind.COST:
        return {"costs_bps": list(DEFAULT_COSTS_BPS)}
    return {}


def _kind_eligible(code: str, kind: ValidationKind) -> bool:
    """A sweep is only meaningful if the strategy actually reads the param."""
    if kind in (ValidationKind.PBO, ValidationKind.SENSITIVITY):
        return strategy_reads_lookback(code)
    if kind == ValidationKind.COST:
        return strategy_reads_parameter(code, SLIPPAGE_PARAMETER)
    return True


def _latest_version(db: Session, strategy_id: UUID) -> StrategyVersion | None:
    return db.scalars(
        select(StrategyVersion)
        .where(StrategyVersion.strategy_id == strategy_id)
        .order_by(StrategyVersion.version.desc())
    ).first()


def _latest_completed_backtest(db: Session, version_id: UUID) -> Backtest | None:
    return db.scalars(
        select(Backtest)
        .where(
            Backtest.strategy_version_id == version_id,
            Backtest.status == BacktestStatus.COMPLETED,
        )
        .order_by(Backtest.created_at.desc())
    ).first()


def _gate_open_reason(
    db: Session, strategy_id: UUID, version_id: UUID, kind: ValidationKind
) -> str | None:
    """Return a reason_code when the kind still needs a run, else None.

    ``None`` means the gate is satisfied (latest completed run passed with no
    error) or already in flight — no card needed.
    """
    rows = list(
        db.execute(
            select(
                ValidationRun.status,
                ValidationRun.passed,
                ValidationRun.error,
                ValidationRun.created_at,
            )
            .where(
                ValidationRun.strategy_id == strategy_id,
                ValidationRun.strategy_version_id == version_id,
                ValidationRun.kind == kind,
            )
            .order_by(ValidationRun.created_at.desc())
        ).all()
    )
    if not rows:
        return "never_run"
    if any(status in _INFLIGHT_STATUSES for status, _passed, _error, _created in rows):
        return None
    latest_status, passed, error, _created = rows[0]
    if latest_status == ValidationRunStatus.COMPLETED and passed and error is None:
        return None
    return "not_passed"


def _discipline_reasons(db: Session, family_id: UUID) -> list[str]:
    """Advisory discipline cards derived from family-wide trial history."""
    reasons: list[str] = []
    trial_rows = list(
        db.execute(
            select(ExperimentTrial.data_snapshot_id, ExperimentTrial.parameter_hash).where(
                ExperimentTrial.strategy_family == family_id
            )
        ).all()
    )
    snapshot_counts: dict[UUID | None, list[str]] = {}
    for snapshot_id, parameter_hash in trial_rows:
        snapshot_counts.setdefault(snapshot_id, []).append(parameter_hash)
    for snapshot_id, hashes in snapshot_counts.items():
        non_empty = [h for h in hashes if h]
        if non_empty and (len(non_empty) - len(set(non_empty))) > 0:
            reasons.append("duplicate_parameters")
            break
    used_ids = [sid for sid in snapshot_counts if sid is not None]
    if used_ids:
        superseded = db.scalars(
            select(DataSnapshot.id).where(
                DataSnapshot.id.in_(used_ids),
                DataSnapshot.superseded_by.is_not(None),
            )
        ).first()
        if superseded is not None:
            reasons.append("superseded_snapshot")
    return reasons


def _card(**fields: Any) -> dict[str, Any]:
    assert set(fields) <= CARD_KEYS, f"suggestion 卡片出现白名单外字段: {set(fields) - CARD_KEYS}"
    return fields


def derive_suggestions(db: Session, strategy_id: UUID) -> list[dict[str, Any]]:
    """Deterministic actionable cards for a strategy, newest-version scoped.

    Returns an empty list for a missing strategy or one with no versions
    (honest empty — the panel shows an empty state, never fabricated advice).
    """
    strategy = db.get(Strategy, strategy_id)
    if strategy is None:
        return []
    if strategy.status == StrategyStatus.ARCHIVED:
        # Frozen strategy: stop suggesting work on it.
        return []
    version = _latest_version(db, strategy_id)
    if version is None:
        return []

    cards: list[dict[str, Any]] = []
    template = _latest_completed_backtest(db, version.id)

    if template is not None:
        for kind in _SUGGESTIBLE_KINDS:
            if not _kind_eligible(version.code, kind):
                continue
            reason = _gate_open_reason(db, strategy_id, version.id, kind)
            if reason is None:
                continue
            cards.append(
                _card(
                    key=f"run_validation:{kind.value}",
                    action=ACTION_RUN_VALIDATION,
                    executable=True,
                    validation_kind=kind.value,
                    strategy_version_id=version.id,
                    target_version=version.version,
                    template_backtest_id=template.id,
                    params=_kind_params(kind),
                    reason_code=reason,
                )
            )
    else:
        cards.append(
            _card(
                key="guide:backtest_first",
                action=ACTION_GUIDE,
                executable=False,
                strategy_version_id=version.id,
                target_version=version.version,
                template_backtest_id=None,
                params={},
                reason_code="backtest_first",
            )
        )

    family_id = strategy.family_id or strategy.id
    for reason in _discipline_reasons(db, family_id):
        cards.append(
            _card(
                key=f"discipline:{reason}",
                action=ACTION_DISCIPLINE,
                executable=False,
                validation_kind=None,
                strategy_version_id=None,
                target_version=None,
                template_backtest_id=None,
                params={},
                reason_code=reason,
            )
        )

    return cards
