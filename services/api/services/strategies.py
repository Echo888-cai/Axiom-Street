from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from quant.strategy_sdk.spy_200dma import DEFAULT_STRATEGY_CODE, default_builder_config
from services.api.models import AuditLog, Strategy, StrategyStatus, StrategyVersion
from services.api.schemas import StrategyCreate, StrategyUpdate, StrategyVersionCreate


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


def list_strategies(db: Session) -> list[Strategy]:
    return list(db.scalars(select(Strategy).order_by(Strategy.updated_at.desc())).all())


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
