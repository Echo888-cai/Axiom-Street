from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.schemas import (
    StrategyCreate,
    StrategyOut,
    StrategyPage,
    StrategyUpdate,
    StrategyVersionCreate,
    StrategyVersionOut,
    TrialStatsOut,
)
from services.api.services import strategies as strategy_service

router = APIRouter(prefix="/strategies", tags=["strategies"])


def _to_out(db: Session, strategy) -> StrategyOut:
    latest = strategy_service.latest_version(db, strategy.id)
    return StrategyOut(
        id=strategy.id,
        name=strategy.name,
        description=strategy.description,
        status=strategy.status,
        asset_class=strategy.asset_class,
        benchmark=strategy.benchmark,
        family_id=strategy.family_id,
        created_at=strategy.created_at,
        updated_at=strategy.updated_at,
        latest_version=StrategyVersionOut.model_validate(latest) if latest else None,
    )


@router.get("", response_model=StrategyPage)
def list_strategies(
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> StrategyPage:
    rows, total = strategy_service.list_strategies(db, limit=limit, offset=offset)
    return StrategyPage(
        items=[_to_out(db, s) for s in rows], total=total, limit=limit, offset=offset
    )


@router.post("", response_model=StrategyOut, status_code=201)
def create_strategy(payload: StrategyCreate, db: Session = Depends(get_db)) -> StrategyOut:
    strategy = strategy_service.create_strategy(db, payload)
    return _to_out(db, strategy)


@router.get("/{strategy_id}", response_model=StrategyOut)
def get_strategy(strategy_id: UUID, db: Session = Depends(get_db)) -> StrategyOut:
    return _to_out(db, strategy_service.get_strategy(db, strategy_id))


@router.patch("/{strategy_id}", response_model=StrategyOut)
def update_strategy(
    strategy_id: UUID, payload: StrategyUpdate, db: Session = Depends(get_db)
) -> StrategyOut:
    return _to_out(db, strategy_service.update_strategy(db, strategy_id, payload))


@router.delete("/{strategy_id}", status_code=204)
def delete_strategy(strategy_id: UUID, db: Session = Depends(get_db)) -> None:
    strategy_service.delete_strategy(db, strategy_id)


@router.get("/{strategy_id}/trial-stats", response_model=TrialStatsOut)
def get_trial_stats(strategy_id: UUID, db: Session = Depends(get_db)) -> TrialStatsOut:
    return TrialStatsOut.model_validate(strategy_service.trial_stats(db, strategy_id))


@router.get("/{strategy_id}/versions", response_model=list[StrategyVersionOut])
def list_versions(strategy_id: UUID, db: Session = Depends(get_db)) -> list[StrategyVersionOut]:
    return [
        StrategyVersionOut.model_validate(v)
        for v in strategy_service.list_versions(db, strategy_id)
    ]


@router.post("/{strategy_id}/versions", response_model=StrategyVersionOut, status_code=201)
def create_version(
    strategy_id: UUID, payload: StrategyVersionCreate, db: Session = Depends(get_db)
) -> StrategyVersionOut:
    return StrategyVersionOut.model_validate(
        strategy_service.create_version(db, strategy_id, payload)
    )
