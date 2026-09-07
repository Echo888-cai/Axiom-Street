from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.schemas import CopilotContextOut
from services.api.services import copilot as copilot_service

router = APIRouter(prefix="/copilot", tags=["copilot"])

_DETAIL_BY_RESOURCE = {"strategy": "策略不存在", "backtest": "回测不存在"}


@router.get("/context", response_model=CopilotContextOut)
def get_context(
    db: Session = Depends(get_db),
    resource: Literal["strategy", "backtest"] = Query(...),
    resource_id: UUID = Query(..., alias="id", description="策略或回测 UUID"),
) -> CopilotContextOut:
    context = copilot_service.build_context(db, resource, resource_id)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_DETAIL_BY_RESOURCE[resource]
        )
    provider = copilot_service.get_provider()
    context["provider"] = {"name": provider.name, "enabled": provider.enabled}
    return CopilotContextOut.model_validate(context)
