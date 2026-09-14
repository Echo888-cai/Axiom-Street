from __future__ import annotations

from collections import defaultdict
from statistics import mean, pvariance
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from quant.strategy_sdk.spy_200dma import DEFAULT_STRATEGY_CODE, default_builder_config
from services.api.db import Base
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
    db: Session,
    *,
    workspace_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    q: str | None = None,
    status_filter: StrategyStatus | None = None,
) -> tuple[list[Strategy], int]:
    filters: list[Any] = []
    if workspace_id is not None:
        filters.append(Strategy.workspace_id == workspace_id)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        filters.append((Strategy.name.ilike(like)) | (Strategy.description.ilike(like)))
    if status_filter is not None:
        filters.append(Strategy.status == status_filter)
    total_stmt = select(func.count()).select_from(Strategy)
    rows_stmt = select(Strategy).order_by(Strategy.updated_at.desc())
    for cond in filters:
        total_stmt = total_stmt.where(cond)
        rows_stmt = rows_stmt.where(cond)
    total = int(db.scalar(total_stmt) or 0)
    rows = list(db.scalars(rows_stmt.offset(offset).limit(limit)).all())
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


def create_strategy(
    db: Session, payload: StrategyCreate, *, workspace_id: UUID | None = None
) -> Strategy:
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
    version_ids = select(StrategyVersion.id).where(StrategyVersion.strategy_id == strategy_id)
    # Only remove unused research drafts. A saved result/ledger must stay auditable.
    # Inspect declared references so adding a new research ledger remains protected.
    for table in Base.metadata.tables.values():
        if table.name == StrategyVersion.__tablename__:
            continue
        for foreign_key in table.foreign_keys:
            target = foreign_key.target_fullname
            if target == "strategies.id":
                condition = foreign_key.parent == strategy_id
            elif target == "strategy_versions.id":
                condition = foreign_key.parent.in_(version_ids)
            else:
                continue
            if db.scalar(select(func.count()).select_from(table).where(condition)):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="该策略已有研究或执行记录，请归档以保留证据，不能永久删除。",
                )
    _audit(
        db,
        actor="local",
        action="Strategy Deleted",
        object_type="strategy",
        object_id=str(strategy.id),
        before={"name": strategy.name},
    )
    db.execute(delete(StrategyVersion).where(StrategyVersion.strategy_id == strategy_id))
    db.execute(delete(Strategy).where(Strategy.id == strategy_id))
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
    from quant.strategy_sdk import normalize_builder_config, strategy_code_hash

    strategy = get_strategy(db, strategy_id)

    # P2.1 versioned rules schema: refuse invalid/out-of-range builder configs
    # and configs claiming a future schema version at the contract boundary.
    try:
        config = normalize_builder_config(payload.config)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "builder_config_invalid", "message": str(exc)},
        ) from exc

    latest = latest_version(db, strategy_id)

    # P2.1 stale-draft conflict detection: a save based on anything but the
    # latest version would silently overwrite newer work.
    if payload.source_version_id is not None:
        source = db.get(StrategyVersion, payload.source_version_id)
        if (
            source is None
            or source.strategy_id != strategy.id
            or latest is None
            or source.id != latest.id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "draft_stale",
                    "message": "草稿已过期：该版本之后已有新版本保存。请重新载入最新版本后再保存，避免覆盖他处的改动。",
                },
            )
        if payload.source_code_hash and payload.source_code_hash != strategy_code_hash(source.code):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "draft_stale_code",
                    "message": "草稿基于的代码已变化，请重新载入最新版本后再保存。",
                },
            )

    next_version = 1 if latest is None else latest.version + 1
    version = StrategyVersion(
        strategy_id=strategy.id,
        version=next_version,
        code=payload.code,
        config=config,
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
