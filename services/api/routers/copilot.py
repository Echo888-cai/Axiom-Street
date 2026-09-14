from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from services.agent import copilot as copilot_service
from services.agent import suggestions as suggestions_service
from services.api.db import get_db
from services.api.models import Strategy
from services.api.schemas import (
    CopilotChatAccepted,
    CopilotChatIn,
    CopilotChatOut,
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

router = APIRouter(prefix="/copilot", tags=["copilot"])


class RuleDraftIn(BaseModel):
    text: str = ""


class RuleCompileIn(BaseModel):
    template: str = "trend"
    symbol: str = "SPY"
    lookback: int | None = 200
    position_pct: float = 100.0
    slippage_bps: float = 5.0
    hypothesis: str = ""


class RuleReviewIn(BaseModel):
    current_code: str = ""
    proposed_code: str = ""
    unsupported: list[str] = []
    source_version_id: str | None = None
    latest_version_id: str | None = None


@router.post("/rules/draft")
def draft_rules(payload: RuleDraftIn) -> dict:
    """P4.1 意图 → 规则草案（确定性、无模型；不支持的语义显式返回）。"""
    from services.agent.rules import draft_rules_from_intent

    return draft_rules_from_intent(payload.text).to_dict()


@router.post("/rules/compile")
def compile_rules(payload: RuleCompileIn) -> dict:
    """P4.1 规则草案 → 确定性代码与配置（不解析任意 Python）。"""
    from services.agent.rules import RuleDraft, compile_trend_rules

    draft = RuleDraft(
        template=payload.template,
        symbol=payload.symbol,
        lookback=payload.lookback,
        position_pct=payload.position_pct,
        slippage_bps=payload.slippage_bps,
        hypothesis=payload.hypothesis or f"{payload.symbol} 趋势跟随",
    )
    try:
        code, config = compile_trend_rules(draft)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": code, "config": config, "unsupported": draft.unsupported}


@router.post("/rules/review")
def review_rules(payload: RuleReviewIn) -> dict:
    """P4.2 变更审查（只读）：差异、语法、依赖、未来数据、版本冲突与出站范围。"""
    from services.agent.rule_review import review_rule_change

    return review_rule_change(
        current_code=payload.current_code,
        proposed_code=payload.proposed_code,
        unsupported=payload.unsupported,
        source_version_id=payload.source_version_id,
        latest_version_id=payload.latest_version_id,
    )


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


@router.get("/chat", response_model=list[CopilotChatOut])
def chat_history(
    db: Session = Depends(get_db),
    strategy_id: UUID = Query(...),
    limit: int = Query(30, ge=1, le=100),
) -> list[CopilotChatOut]:
    rows = copilot_service.list_chat_messages(db, strategy_id, limit=limit)
    return [CopilotChatOut.model_validate(row) for row in rows]


@router.post("/chat", response_model=CopilotChatAccepted, status_code=status.HTTP_202_ACCEPTED)
def chat(payload: CopilotChatIn, db: Session = Depends(get_db)) -> CopilotChatAccepted:
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
    from services.worker.tasks import run_chat_task

    run_chat_task.delay(payload.resource, str(payload.id), payload.message)
    return CopilotChatAccepted(status="queued")


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


@router.get("/eval")
def copilot_eval() -> dict:
    """P4.4 固定评测集：缺证据/注入/幻觉/过期数据；只报告，不改变已发布能力。"""
    from services.agent.copilot.eval import run_eval

    return run_eval()


@router.get("/eval/citations")
def citation_check(text: str = "", allowed_ids: str = "") -> dict:
    """P4.4 引用校验：模型引用的结果 ID 必须来自既有台账，否则判虚构。"""
    from services.agent.copilot.eval import validate_citations

    ids = [item.strip() for item in allowed_ids.split(",") if item.strip()]
    return validate_citations(text, ids).to_dict()
