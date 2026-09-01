from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.schemas import StrategyVersionOut
from services.api.services import strategies as strategy_service

router = APIRouter(tags=["strategy-versions"])


@router.get("/strategy-versions/{version_id}", response_model=StrategyVersionOut)
def get_strategy_version(version_id: UUID, db: Session = Depends(get_db)) -> StrategyVersionOut:
    return StrategyVersionOut.model_validate(strategy_service.get_version(db, version_id))
