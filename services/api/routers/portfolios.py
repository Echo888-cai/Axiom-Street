"""Portfolio configuration and single-period attribution API (E8-1)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from quant.portfolio.attribution import AttributionObservation, compute_brinson_attribution
from services.api.db import get_db
from services.api.models import (
    Portfolio,
    PortfolioAllocation,
    PortfolioAttribution,
    Strategy,
)
from services.api.schemas import (
    PortfolioAllocationIn,
    PortfolioAllocationOut,
    PortfolioAttributionIn,
    PortfolioAttributionOut,
    PortfolioCreate,
    PortfolioOut,
)

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


def _portfolio(db: Session, portfolio_id: UUID):
    row = db.get(Portfolio, portfolio_id)
    if row is None:
        raise HTTPException(status_code=404, detail="组合不存在")
    return row


@router.post("", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: PortfolioCreate, db: Session = Depends(get_db)) -> PortfolioOut:
    row = Portfolio(
        name=payload.name,
        base_currency=payload.base_currency,
        initial_capital=payload.initial_capital,
    )
    db.add(row)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="组合名称已存在") from exc
    db.refresh(row)
    return PortfolioOut.model_validate(row)


@router.get("", response_model=list[PortfolioOut])
def list_portfolios(
    limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)
) -> list[PortfolioOut]:
    rows = db.scalars(select(Portfolio).order_by(Portfolio.updated_at.desc()).limit(limit)).all()
    return [PortfolioOut.model_validate(row) for row in rows]


@router.post(
    "/{portfolio_id}/allocations",
    response_model=PortfolioAllocationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_allocation(
    portfolio_id: UUID, payload: PortfolioAllocationIn, db: Session = Depends(get_db)
) -> PortfolioAllocationOut:
    portfolio = _portfolio(db, portfolio_id)
    if db.get(Strategy, payload.strategy_id) is None:
        raise HTTPException(status_code=404, detail="策略不存在")
    if payload.effective_to is not None and payload.effective_to < payload.effective_from:
        raise HTTPException(status_code=422, detail="effective_to 不能早于 effective_from")
    row = PortfolioAllocation(
        portfolio_id=portfolio.id,
        strategy_id=payload.strategy_id,
        weight=payload.weight,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
    )
    db.add(row)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="该组合已有相同策略和生效日配置") from exc
    db.refresh(row)
    return PortfolioAllocationOut.model_validate(row)


@router.get("/{portfolio_id}/allocations", response_model=list[PortfolioAllocationOut])
def list_allocations(
    portfolio_id: UUID, db: Session = Depends(get_db)
) -> list[PortfolioAllocationOut]:
    _portfolio(db, portfolio_id)
    rows = db.scalars(
        select(PortfolioAllocation)
        .where(PortfolioAllocation.portfolio_id == portfolio_id)
        .order_by(PortfolioAllocation.effective_from.desc(), PortfolioAllocation.strategy_id)
    ).all()
    return [PortfolioAllocationOut.model_validate(row) for row in rows]


@router.post(
    "/{portfolio_id}/attribution",
    response_model=PortfolioAttributionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_attribution(
    portfolio_id: UUID, payload: PortfolioAttributionIn, db: Session = Depends(get_db)
) -> PortfolioAttributionOut:
    _portfolio(db, portfolio_id)
    existing = db.scalar(
        select(PortfolioAttribution).where(
            PortfolioAttribution.portfolio_id == portfolio_id,
            PortfolioAttribution.as_of == payload.as_of,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="该日期的归因快照已存在且不可覆盖")
    allocations = db.scalars(
        select(PortfolioAllocation).where(
            PortfolioAllocation.portfolio_id == portfolio_id,
            PortfolioAllocation.effective_from <= payload.as_of,
            (
                PortfolioAllocation.effective_to.is_(None)
                | (PortfolioAllocation.effective_to >= payload.as_of)
            ),
        )
    ).all()
    by_strategy = {str(row.strategy_id): row for row in allocations}
    return_ids = {str(row.strategy_id) for row in payload.returns}
    if set(by_strategy) != return_ids:
        raise HTTPException(status_code=409, detail="归因收益必须覆盖当前全部策略配置,且不能多传")
    observations = [
        AttributionObservation(
            strategy_id=str(row.strategy_id),
            weight=by_strategy[str(row.strategy_id)].weight,
            strategy_return=row.strategy_return,
            benchmark_return=row.benchmark_return,
        )
        for row in payload.returns
    ]
    try:
        result = compute_brinson_attribution(observations)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    inputs = {
        "weights": {str(row.strategy_id): row.weight for row in allocations},
        "returns": [row.model_dump(mode="json") for row in payload.returns],
        "benchmark_method": "equal_weight_strategy_baseline",
    }
    snapshot = PortfolioAttribution(
        portfolio_id=portfolio_id,
        as_of=payload.as_of,
        portfolio_return=result.portfolio_return,
        benchmark_return=result.benchmark_return,
        allocation_effect=result.allocation_effect,
        selection_effect=result.selection_effect,
        interaction_effect=result.interaction_effect,
        active_return=result.active_return,
        inputs=inputs,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return PortfolioAttributionOut.model_validate(snapshot)


@router.get("/{portfolio_id}/attribution", response_model=list[PortfolioAttributionOut])
def list_attribution(
    portfolio_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[PortfolioAttributionOut]:
    _portfolio(db, portfolio_id)
    rows = db.scalars(
        select(PortfolioAttribution)
        .where(PortfolioAttribution.portfolio_id == portfolio_id)
        .order_by(PortfolioAttribution.as_of.desc())
        .limit(limit)
    ).all()
    return [PortfolioAttributionOut.model_validate(row) for row in rows]
