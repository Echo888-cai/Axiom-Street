from __future__ import annotations

from collections import defaultdict
from statistics import mean, pvariance
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from quant.strategy_sdk.spy_200dma import DEFAULT_STRATEGY_CODE, default_builder_config
from services.api.models import (
    AuditLog,
    DataSnapshot,
    ExperimentTrial,
    Strategy,
    StrategyStatus,
    StrategyVersion,
)
from services.api.schemas import StrategyCreate, StrategyUpdate, StrategyVersionCreate
from services.api.status_machine import assert_client_status_transition


def _audit(
    db: Session,
    *,
    actor: str,
    action: str,
    object_type: str,
    object_id: str,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor=actor,
            action=action,
            object_type=object_type,
            object_id=object_id,
            before=before,
            after=after,
        )
    )


def list_strategies(
    db: Session, *, limit: int = 100, offset: int = 0
) -> tuple[list[Strategy], int]:
    total = int(db.scalar(select(func.count()).select_from(Strategy)) or 0)
    rows = list(
        db.scalars(
            select(Strategy).order_by(Strategy.updated_at.desc()).offset(offset).limit(limit)
        ).all()
    )
    return rows, total


def get_strategy(db: Session, strategy_id: UUID) -> Strategy:
    strategy = db.get(Strategy, strategy_id)
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="策略不存在")
    return strategy


def latest_version(db: Session, strategy_id: UUID) -> StrategyVersion | None:
    return db.scalars(
        select(StrategyVersion)
        .where(StrategyVersion.strategy_id == strategy_id)
        .order_by(StrategyVersion.version.desc())
        .limit(1)
    ).first()


def create_strategy(db: Session, payload: StrategyCreate) -> Strategy:
    strategy = Strategy(
        name=payload.name,
        description=payload.description,
        status=StrategyStatus.DRAFT,
        asset_class=payload.asset_class,
        benchmark=payload.benchmark,
    )
    db.add(strategy)
    db.flush()
    if strategy.family_id is None:
        strategy.family_id = strategy.id

    code = payload.code or DEFAULT_STRATEGY_CODE
    config = payload.config or default_builder_config()
    version = StrategyVersion(
        strategy_id=strategy.id,
        version=1,
        code=code,
        config=config,
        commit_message=payload.commit_message or "Initial version",
        created_by="local",
    )
    db.add(version)
    _audit(
        db,
        actor="local",
        action="Strategy Created",
        object_type="strategy",
        object_id=str(strategy.id),
        after={"name": strategy.name},
    )
    db.commit()
    db.refresh(strategy)
    return strategy


def update_strategy(db: Session, strategy_id: UUID, payload: StrategyUpdate) -> Strategy:
    strategy = get_strategy(db, strategy_id)
    before = {"name": strategy.name, "status": strategy.status.value}
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        assert_client_status_transition(strategy.status, data["status"])
    for key, value in data.items():
        setattr(strategy, key, value)
    _audit(
        db,
        actor="local",
        action="Strategy Modified",
        object_type="strategy",
        object_id=str(strategy.id),
        before=before,
        after=data,
    )
    db.commit()
    db.refresh(strategy)
    return strategy


def delete_strategy(db: Session, strategy_id: UUID) -> None:
    strategy = get_strategy(db, strategy_id)
    _audit(
        db,
        actor="local",
        action="Strategy Deleted",
        object_type="strategy",
        object_id=str(strategy.id),
        before={"name": strategy.name},
    )
    db.delete(strategy)
    db.commit()


def list_versions(db: Session, strategy_id: UUID) -> list[StrategyVersion]:
    get_strategy(db, strategy_id)
    return list(
        db.scalars(
            select(StrategyVersion)
            .where(StrategyVersion.strategy_id == strategy_id)
            .order_by(StrategyVersion.version.desc())
        ).all()
    )


def create_version(
    db: Session, strategy_id: UUID, payload: StrategyVersionCreate
) -> StrategyVersion:
    strategy = get_strategy(db, strategy_id)
    latest = latest_version(db, strategy_id)
    next_version = 1 if latest is None else latest.version + 1
    version = StrategyVersion(
        strategy_id=strategy.id,
        version=next_version,
        code=payload.code,
        config=payload.config,
        commit_message=payload.commit_message or f"v{next_version}",
        created_by="local",
    )
    db.add(version)
    strategy.status = StrategyStatus.DRAFT
    _audit(
        db,
        actor="local",
        action="Strategy Modified",
        object_type="strategy_version",
        object_id=str(strategy.id),
        after={"version": next_version, "commit_message": version.commit_message},
    )
    db.commit()
    db.refresh(version)
    return version


def get_version(db: Session, version_id: UUID) -> StrategyVersion:
    version = db.get(StrategyVersion, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="策略版本不存在")
    return version


def trial_stats(db: Session, strategy_id: UUID) -> dict:
    strategy = get_strategy(db, strategy_id)
    family_id = strategy.family_id or strategy.id
    trials = list(
        db.scalars(
            select(ExperimentTrial).where(ExperimentTrial.strategy_family == family_id)
        ).all()
    )
    grouped: dict[UUID | None, list[ExperimentTrial]] = defaultdict(list)
    for trial in trials:
        grouped[trial.data_snapshot_id].append(trial)

    by_snapshot = []
    for snapshot_id, rows in grouped.items():
        sharpes = [t.observed_sharpe for t in rows if t.observed_sharpe is not None]
        hashes = [t.parameter_hash for t in rows if t.parameter_hash]
        dup = len(hashes) - len(set(hashes))
        snap = db.get(DataSnapshot, snapshot_id) if snapshot_id else None
        by_snapshot.append(
            {
                "data_snapshot_id": snapshot_id,
                "snapshot_key": snap.snapshot_key if snap else None,
                "count": len(rows),
                "sharpe_mean": mean(sharpes) if sharpes else None,
                "sharpe_var": pvariance(sharpes)
                if len(sharpes) >= 2
                else (0.0 if sharpes else None),
                "sharpe_max": max(sharpes) if sharpes else None,
                "duplicate_parameter_hashes": dup,
            }
        )
    by_snapshot.sort(key=lambda row: int(row["count"] or 0), reverse=True)
    return {
        "strategy_id": strategy.id,
        "family_id": family_id,
        "total_trials": len(trials),
        "by_snapshot": by_snapshot,
    }
