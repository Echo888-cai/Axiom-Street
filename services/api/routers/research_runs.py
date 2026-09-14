"""Bounded research runs API (P4.3)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.services import research_runs as runs_service

router = APIRouter(prefix="/research-runs", tags=["research-runs"])


class ResearchRunIn(BaseModel):
    goal: str = ""
    strategy_id: UUID | None = None
    budget: dict[str, Any] = Field(default_factory=dict)


@router.post("", status_code=http_status.HTTP_201_CREATED)
def create_run(payload: ResearchRunIn, db: Session = Depends(get_db)) -> dict:
    run = runs_service.create_run(
        db, goal=payload.goal, strategy_id=payload.strategy_id, budget=payload.budget
    )
    return runs_service.run_state(db, run.id)


@router.get("/{run_id}")
def get_run(run_id: UUID, db: Session = Depends(get_db)) -> dict:
    return runs_service.run_state(db, run_id)


@router.post("/{run_id}/step")
def advance(run_id: UUID, db: Session = Depends(get_db)) -> dict:
    run = runs_service.advance_run(db, run_id)
    return runs_service.run_state(db, run.id)


@router.post("/{run_id}/pause")
def pause(run_id: UUID, db: Session = Depends(get_db)) -> dict:
    run = runs_service.pause_run(db, run_id)
    return runs_service.run_state(db, run.id)


@router.post("/{run_id}/resume")
def resume(run_id: UUID, db: Session = Depends(get_db)) -> dict:
    run = runs_service.resume_run(db, run_id)
    return runs_service.run_state(db, run.id)


@router.post("/{run_id}/cancel")
def cancel(run_id: UUID, db: Session = Depends(get_db)) -> dict:
    run = runs_service.cancel_run(db, run_id)
    return runs_service.run_state(db, run.id)
