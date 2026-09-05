from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.models import ValidationKind
from services.api.schemas import (
    ValidationCreate,
    ValidationPage,
    ValidationRunOut,
    ValidationSpecOut,
)
from services.api.services import validation as validation_service
from services.api.services.validation_spec import all_specs, params_schema_for

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


@router.post("", response_model=ValidationRunOut, status_code=201)
def create_validation_run(
    payload: ValidationCreate, db: Session = Depends(get_db)
) -> ValidationRunOut:
    return validation_service.to_out(validation_service.create_validation_run(db, payload))


# Legacy endpoints for backward compatibility — delegate to unified endpoint
def _legacy_payload(kind: str, payload: dict) -> ValidationCreate:
    known_keys = {"strategy_version_id", "backtest_id"}
    params = {k: v for k, v in payload.items() if k not in known_keys}
    return ValidationCreate(
        kind=kind,
        strategy_version_id=payload["strategy_version_id"],
        backtest_id=payload.get("backtest_id"),
        params=params,
    )


@router.post("/pbo", response_model=ValidationRunOut, status_code=201)
def create_pbo_scan(payload: dict, db: Session = Depends(get_db)) -> ValidationRunOut:
    return validation_service.to_out(
        validation_service.create_validation_run(db, _legacy_payload("pbo", payload))
    )


@router.post("/sensitivity", response_model=ValidationRunOut, status_code=201)
def create_sensitivity_scan(payload: dict, db: Session = Depends(get_db)) -> ValidationRunOut:
    return validation_service.to_out(
        validation_service.create_validation_run(db, _legacy_payload("sensitivity", payload))
    )


@router.post("/cost", response_model=ValidationRunOut, status_code=201)
def create_cost_scan(payload: dict, db: Session = Depends(get_db)) -> ValidationRunOut:
    return validation_service.to_out(
        validation_service.create_validation_run(db, _legacy_payload("cost", payload))
    )


@router.post("/bootstrap", response_model=ValidationRunOut, status_code=201)
def create_bootstrap(payload: dict, db: Session = Depends(get_db)) -> ValidationRunOut:
    return validation_service.to_out(
        validation_service.create_validation_run(db, _legacy_payload("bootstrap", payload))
    )


@router.post("/regime", response_model=ValidationRunOut, status_code=201)
def create_regime(payload: dict, db: Session = Depends(get_db)) -> ValidationRunOut:
    return validation_service.to_out(
        validation_service.create_validation_run(db, _legacy_payload("regime", payload))
    )


@router.post("/spa", response_model=ValidationRunOut, status_code=201)
def create_spa(payload: dict, db: Session = Depends(get_db)) -> ValidationRunOut:
    return validation_service.to_out(
        validation_service.create_validation_run(db, _legacy_payload("spa", payload))
    )


@router.post("/walk-forward", response_model=ValidationRunOut, status_code=201)
def create_walk_forward(payload: dict, db: Session = Depends(get_db)) -> ValidationRunOut:
    return validation_service.to_out(
        validation_service.create_validation_run(db, _legacy_payload("walk_forward", payload))
    )


@router.get("/{run_id}", response_model=ValidationRunOut)
def get_validation_run(run_id: UUID, db: Session = Depends(get_db)) -> ValidationRunOut:
    return validation_service.to_out(validation_service.get_validation_run(db, run_id))


@router.get("/specs", response_model=list[ValidationSpecOut])
def get_validation_specs() -> list[ValidationSpecOut]:
    specs = []
    for spec in all_specs():
        schema = params_schema_for(spec.kind)
        specs.append(
            ValidationSpecOut(
                kind=spec.kind,
                display_name=spec.display_name,
                description=spec.description,
                auto_on_backtest=spec.auto_on_backtest,
                params_schema=schema.model_json_schema(),
            )
        )
    return specs
