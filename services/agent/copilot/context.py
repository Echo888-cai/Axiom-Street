"""Read-only context assembly for the AI copilot.

Projection over the trial ledger, strategy metadata and validation runs that
feeds the right-rail panel. Write isolation is structural: copilot modules
must not import write-path services or call ORM write APIs (locked by
``tests/unit/test_copilot_isolation.py``).

The outbound privacy boundary is enforced at the column level from day one:
strategy source (``code``/``config``), parameter JSON and market columns are
never selected here, so no future LLM adapter can receive them — only the
aggregate statistics this module emits.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.agent.copilot.trial_facts import trial_facts
from services.api.models import (
    Backtest,
    Strategy,
    StrategyVersion,
    ValidationKind,
    ValidationRun,
)

KIND_ORDER = [kind.value for kind in ValidationKind]


def _v(value: Any) -> Any:
    """Drivers return enum members; normalize to their plain values."""
    return value.value if isinstance(value, Enum) else value


def _strategy_meta(db: Session, strategy_id: UUID) -> dict[str, Any] | None:
    row = (
        db.execute(
            select(Strategy.id, Strategy.name, Strategy.status, Strategy.family_id).where(
                Strategy.id == strategy_id
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "status": _v(row["status"]),
        "family_id": row["family_id"] or row["id"],
    }


def _latest_version(db: Session, strategy_id: UUID) -> int | None:
    return db.execute(
        select(func.max(StrategyVersion.version)).where(StrategyVersion.strategy_id == strategy_id)
    ).scalar()


def _gate_summary(db: Session, strategy_id: UUID) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            ValidationRun.kind,
            ValidationRun.status,
            ValidationRun.passed,
            ValidationRun.finished_at,
            ValidationRun.created_at,
        ).where(ValidationRun.strategy_id == strategy_id)
    ).all()
    latest: dict[str, Any] = {}
    for kind, status, passed, finished_at, created_at in rows:
        name = _v(kind)
        created = created_at or datetime.min
        current = latest.get(name)
        if current is None or created > current["created_at"]:
            latest[name] = {
                "created_at": created,
                "kind": name,
                "status": _v(status),
                "passed": passed,
                "finished_at": finished_at,
            }
    return [
        {k: v for k, v in latest[name].items() if k != "created_at"}
        for name in KIND_ORDER
        if name in latest
    ]


def _strategy_context(db: Session, strategy_id: UUID) -> dict[str, Any] | None:
    meta = _strategy_meta(db, strategy_id)
    if meta is None:
        return None
    by_snapshot = trial_facts(db, meta["family_id"])
    return {
        "strategy_id": meta["id"],
        "strategy_name": meta["name"],
        "strategy_status": meta["status"],
        "family_id": meta["family_id"],
        "latest_version": _latest_version(db, strategy_id),
        "total_trials": sum(row["count"] for row in by_snapshot),
        "by_snapshot": by_snapshot,
        "gates": _gate_summary(db, strategy_id),
    }


def _load_backtest(db: Session, backtest_id: UUID) -> dict[str, Any] | None:
    row = (
        db.execute(
            select(Backtest.id, Backtest.status, Backtest.created_at, StrategyVersion.strategy_id)
            .join(StrategyVersion, StrategyVersion.id == Backtest.strategy_version_id)
            .where(Backtest.id == backtest_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return {
        "id": row["id"],
        "status": _v(row["status"]),
        "created_at": row["created_at"],
        "strategy_id": row["strategy_id"],
    }


def build_context(db: Session, resource: str, resource_id: UUID) -> dict[str, Any] | None:
    """Assemble the copilot context for a strategy or backtest scope.

    Returns ``None`` when the resource (or its strategy) does not exist.
    """
    if resource not in {"strategy", "backtest"}:
        raise ValueError(f"unsupported copilot resource: {resource!r}")
    backtest = None
    if resource == "backtest":
        backtest = _load_backtest(db, resource_id)
        if backtest is None:
            return None
        strategy_id = backtest["strategy_id"]
    else:
        strategy_id = resource_id

    context = _strategy_context(db, strategy_id)
    if context is None:
        return None
    context["resource"] = resource
    context["backtest"] = backtest
    return context
