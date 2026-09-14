"""P5 continuous paper session API."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.services import paper_session as paper_service

router = APIRouter(prefix="/paper-sessions", tags=["paper-sessions"])


class SessionCreate(BaseModel):
    strategy_id: UUID
    name: str = "模拟会话"
    limits: dict[str, Any] = Field(default_factory=dict)
    initial_cash: float = 100_000.0


class BarIn(BaseModel):
    bar_date: date
    signals: list[dict[str, Any]]
    prices: dict[str, float] = Field(default_factory=dict)


class ObservationIn(BaseModel):
    day: date
    signals: dict[str, Any] = Field(default_factory=dict)
    orders: dict[str, Any] = Field(default_factory=dict)
    fills: dict[str, Any] = Field(default_factory=dict)
    fee_slippage: dict[str, Any] = Field(default_factory=dict)
    deviation: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


@router.post("", status_code=http_status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)) -> dict:
    session = paper_service.create_session(
        db,
        strategy_id=payload.strategy_id,
        name=payload.name,
        limits=payload.limits,
        initial_cash=payload.initial_cash,
    )
    return _out(session)


@router.post("/{session_id}/bars")
def process_bar(session_id: UUID, payload: BarIn, db: Session = Depends(get_db)) -> dict:
    return paper_service.on_bar(
        db, session_id, bar_date=payload.bar_date, signals=payload.signals, prices=payload.prices
    )


@router.post("/{session_id}/halt")
def halt(session_id: UUID, db: Session = Depends(get_db)) -> dict:
    return _out(paper_service.set_halt(db, session_id, True))


@router.post("/{session_id}/resume")
def resume(session_id: UUID, db: Session = Depends(get_db)) -> dict:
    return _out(paper_service.set_halt(db, session_id, False))


@router.post("/{session_id}/kill-switch")
def kill_switch(session_id: UUID, enabled: bool = True, db: Session = Depends(get_db)) -> dict:
    return _out(paper_service.set_kill_switch(db, session_id, enabled))


@router.post("/{session_id}/reconcile")
def reconcile(session_id: UUID, db: Session = Depends(get_db)) -> dict:
    return paper_service.reconcile_session(db, session_id)


@router.post("/{session_id}/observations")
def record_observation(
    session_id: UUID, payload: ObservationIn, db: Session = Depends(get_db)
) -> dict:
    row = paper_service.record_daily_observation(
        db,
        session_id,
        day=payload.day,
        signals=payload.signals,
        orders=payload.orders,
        fills=payload.fills,
        fee_slippage=payload.fee_slippage,
        deviation=payload.deviation,
        notes=payload.notes,
    )
    return _out(row)


@router.get("/{session_id}/observation-status")
def status(session_id: UUID, db: Session = Depends(get_db)) -> dict:
    return paper_service.observation_status(db, session_id)


def _out(obj: Any) -> dict:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return {
        "id": str(obj.id),
        "strategy_id": str(obj.strategy_id) if obj.strategy_id else None,
        "name": getattr(obj, "name", ""),
        "status": obj.status.value if hasattr(obj.status, "value") else obj.status,
        "limits": obj.limits,
        "account": obj.account,
        "observation_days": obj.observation_days,
        "kill_switch": obj.kill_switch,
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }
