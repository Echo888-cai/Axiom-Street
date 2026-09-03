from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.models import ValidationKind
from services.api.schemas import (
    BootstrapCreate,
    CostScanCreate,
    PBOScanCreate,
    SensitivityCreate,
    ValidationPage,
    ValidationRunOut,
    WalkForwardCreate,
)
from services.api.services import validation as validation_service

router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("", response_model=ValidationPage)
def list_validation_runs(
    db: Session = Depends(get_db),
    strategy_id: UUID | None = None,
    kind: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ValidationPage:
    kind_enum = None
    if kind:
        try:
            kind_enum = ValidationKind(kind)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未知的验证类型：{kind}",
            ) from exc
    rows, total = validation_service.list_validation_runs(
        db, strategy_id=strategy_id, kind=kind_enum, limit=limit, offset=offset
    )
    return ValidationPage(
        items=[validation_service.to_out(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
        gates=validation_service.validation_gates(),
    )


@router.post("/pbo", response_model=ValidationRunOut, status_code=201)
def create_pbo_scan(payload: PBOScanCreate, db: Session = Depends(get_db)) -> ValidationRunOut:
    return validation_service.to_out(validation_service.create_pbo_scan(db, payload))


@router.post("/sensitivity", response_model=ValidationRunOut, status_code=201)
def create_sensitivity_scan(
    payload: SensitivityCreate, db: Session = Depends(get_db)
) -> ValidationRunOut:
    return validation_service.to_out(validation_service.create_sensitivity_scan(db, payload))


@router.post("/cost", response_model=ValidationRunOut, status_code=201)
def create_cost_scan(payload: CostScanCreate, db: Session = Depends(get_db)) -> ValidationRunOut:
    return validation_service.to_out(validation_service.create_cost_scan(db, payload))


@router.post("/bootstrap", response_model=ValidationRunOut, status_code=201)
def create_bootstrap(payload: BootstrapCreate, db: Session = Depends(get_db)) -> ValidationRunOut:
    return validation_service.to_out(validation_service.create_bootstrap_run(db, payload))


@router.post("/walk-forward", response_model=ValidationRunOut, status_code=201)
def create_walk_forward(
    payload: WalkForwardCreate, db: Session = Depends(get_db)
) -> ValidationRunOut:
    return validation_service.to_out(validation_service.create_walk_forward_run(db, payload))


@router.get("/{run_id}", response_model=ValidationRunOut)
def get_validation_run(run_id: UUID, db: Session = Depends(get_db)) -> ValidationRunOut:
    return validation_service.to_out(validation_service.get_validation_run(db, run_id))
