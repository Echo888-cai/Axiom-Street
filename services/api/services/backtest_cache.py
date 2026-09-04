from __future__ import annotations

import hashlib
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.hashing import canonical_hash
from services.api.models import Backtest, BacktestStatus

_LIVE = (
    BacktestStatus.QUEUED,
    BacktestStatus.STARTING,
    BacktestStatus.RUNNING,
    BacktestStatus.COMPLETED,
)


def code_sha256(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def universe_from_snapshot(snapshot: Any) -> list[str]:
    if not isinstance(snapshot, list):
        return []
    out: list[str] = []
    for item in snapshot:
        if isinstance(item, dict) and item.get("symbol"):
            symbol = str(item["symbol"])
            if symbol not in out:
                out.append(symbol)
    return out


def result_fingerprint(
    *,
    code: str,
    data_snapshot_id: UUID | None,
    engine_version: str,
    start_date: date,
    end_date: date,
    benchmark: str,
    initial_capital: float,
    universe: list[str],
    universe_id: UUID | None,
    parameters: dict[str, Any] | None,
) -> str:
    """Identity of a backtest trial. Same tuple → same experiment, do not re-run."""
    return canonical_hash(
        {
            "code_sha256": code_sha256(code),
            "data_snapshot_id": str(data_snapshot_id) if data_snapshot_id else None,
            "engine_version": engine_version,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "benchmark": benchmark,
            "initial_capital": initial_capital,
            "universe": list(universe),
            "universe_id": str(universe_id) if universe_id else None,
            "parameters": parameters or {},
        }
    )


def find_cached_backtest(db: Session, fingerprint: str) -> Backtest | None:
    stmt = (
        select(Backtest)
        .where(
            Backtest.result_fingerprint == fingerprint,
            Backtest.status.in_(_LIVE),
        )
        .order_by(Backtest.created_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()
