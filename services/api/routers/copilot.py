from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.models import Strategy
from services.api.schemas import (
    CopilotContextOut,
    CopilotInsightOut,
    CopilotSuggestAccepted,
    CopilotSuggestIn,
    CopilotSuggestionCard,
    CopilotSuggestionOut,
    CopilotSuggestionsOut,
    CopilotSynthesizeAccepted,
    CopilotSynthesizeIn,
)
from services.agent import copilot as copilot_service
from services.agent import suggestions as suggestions_service

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


@router.post(
    "/synthesize",
    response_model=CopilotSynthesizeAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def synthesize(
    payload: CopilotSynthesizeIn,
    db: Session = Depends(get_db),
) -> CopilotSynthesizeAccepted:
    """Enqueue one model synthesize pass for the scope's strategy (P5-2).

    The API only enqueues: the worker task performs the outbound DeepSeek call
    and records the ledger row. Provider disabled (no key / noop) fails loud
    with 503 before anything is queued.
    """
    context = copilot_service.build_context(db, payload.resource, payload.id)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_DETAIL_BY_RESOURCE[payload.resource]
        )
    provider = copilot_service.get_provider()
    if not provider.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"模型 {provider.name} 未启用:未配置 API key(无 key 即关闭)",
        )
    # Lazy import, mirroring services/backtests.py: the API process never boots
    # the Celery app at import time; enqueue only.
    from services.worker.tasks import run_synthesize_task

    run_synthesize_task.delay(payload.resource, str(payload.id))
    return CopilotSynthesizeAccepted(status="queued")


@router.get("/insights", response_model=list[CopilotInsightOut])
def insights(
    db: Session = Depends(get_db),
    strategy_id: UUID = Query(...),
    limit: int = Query(10, ge=1, le=50),
) -> list[CopilotInsightOut]:
    """Synthesize ledger for a strategy, newest first (P5-2)."""
    rows = copilot_service.list_insights(db, strategy_id, limit=limit)
    return [CopilotInsightOut.model_validate(row) for row in rows]


@router.get("/suggestions", response_model=CopilotSuggestionsOut)
def suggestions(
    db: Session = Depends(get_db),
    strategy_id: UUID = Query(...),
) -> CopilotSuggestionsOut:
    """Deterministic actionable cards for a strategy (P5-3).

    Stateless derivation on every call — the executable source of truth for
    what the copilot can recommend. The model (when enabled) only picks within
    these cards.
    """
    if db.get(Strategy, strategy_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="策略不存在")
    cards = [
        CopilotSuggestionCard.model_validate(c)
        for c in suggestions_service.derive_suggestions(db, strategy_id)
    ]
    return CopilotSuggestionsOut(candidates=cards)


@router.get(
    "/suggestions/recommendation",
    response_model=Optional[CopilotSuggestionOut],
)
def suggestion_recommendation(
    db: Session = Depends(get_db),
    strategy_id: UUID = Query(...),
) -> Optional[CopilotSuggestionOut]:
    """Newest model priority pick for a strategy, or null when none yet."""
    row = copilot_service.latest_suggestion(db, strategy_id)
    if row is None:
        return None
    return CopilotSuggestionOut.model_validate(row)


@router.post(
    "/suggest",
    response_model=CopilotSuggestAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def suggest(
    payload: CopilotSuggestIn,
    db: Session = Depends(get_db),
) -> CopilotSuggestAccepted:
    """Enqueue one model priority pick over the deterministic candidates (P5-3).

    API only enqueues; the worker derives candidates, calls the provider
    constrained to that set, and records one row in ``copilot_suggestions``.
    Provider disabled fails loud with 503 before anything is queued.
    """
    context = copilot_service.build_context(db, payload.resource, payload.id)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_DETAIL_BY_RESOURCE[payload.resource]
        )
    provider = copilot_service.get_provider()
    if not provider.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"模型 {provider.name} 未启用:未配置 API key(无 key 即关闭)",
        )
    from services.worker.tasks import run_suggest_task

    run_suggest_task.delay(payload.resource, str(payload.id))
    return CopilotSuggestAccepted(status="queued")
