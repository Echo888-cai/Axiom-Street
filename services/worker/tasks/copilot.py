"""Copilot synthesize task (P5-2): one DeepSeek call, persisted to the ledger.

Orchestrates the outbound model call worker-side: re-reads the read-only
context (aggregate statistics only — ``copilot/context.py`` never selects
strategy source, parameter JSON or market columns), calls the configured
provider, and records exactly one row in the copilot's own ledger table
``copilot_insights``. The API layer only enqueues this task; it never dials
out and never writes.

Isolation (enforced by ``tests/unit/test_copilot_isolation.py`` for this file):
the only ORM write calls allowed anywhere in this module are inside
``_record_insight``.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import UUID

from services.api.models import (
    CopilotInsight,
    CopilotInsightStatus,
    CopilotSuggestion,
    CopilotSuggestionStatus,
)
from services.agent.copilot.context import build_context
from services.agent.copilot.providers import CopilotProviderError, get_provider
from services.agent.suggestions import derive_suggestions
from services.api.settings import get_settings
from services.worker import tasks as _tasks
from services.worker.celery_app import celery_app

_DETAIL_BY_RESOURCE = {"strategy": "策略不存在", "backtest": "回测不存在"}
_MAX_ERROR_CHARS = 500


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _record_insight(
    db,
    strategy_id: UUID,
    *,
    status: CopilotInsightStatus,
    model: str,
    narrative: str = "",
    error: str | None = None,
    duration_ms: int | None = None,
) -> dict:
    """Single write point for the ledger. Only ORM write calls allowed in this file."""
    row = CopilotInsight(
        strategy_id=strategy_id,
        status=status,
        model=model,
        narrative=narrative,
        error=error,
        duration_ms=duration_ms,
        finished_at=_now(),
    )
    db.add(row)
    db.commit()
    return {"insight_id": str(row.id), "status": status.value.lower()}


def _record_suggestion(
    db,
    strategy_id: UUID,
    *,
    status: CopilotSuggestionStatus,
    model: str,
    picked_id: str | None = None,
    reason: str = "",
    error: str | None = None,
    duration_ms: int | None = None,
) -> dict:
    """Single write point for the suggestion ledger. Write-call-exempt helper."""
    row = CopilotSuggestion(
        strategy_id=strategy_id,
        status=status,
        model=model,
        picked_id=picked_id,
        reason=reason,
        error=error,
        duration_ms=duration_ms,
        finished_at=_now(),
    )
    db.add(row)
    db.commit()
    return {"suggestion_id": str(row.id), "status": status.value.lower()}


def execute_synthesize(resource: str, resource_id: str) -> dict:
    """Run one synthesize pass and record exactly one ledger row."""
    # Celery delivers JSON strings; convert before the typed query.
    try:
        scope_id = UUID(resource_id)
    except (ValueError, AttributeError):
        return {"status": "not_found", "detail": _DETAIL_BY_RESOURCE[resource]}
    # Session as a context manager: no explicit ``.close`` call in this file
    # (the isolation lock treats the ``close`` column name as out of bounds).
    with _tasks.SessionLocal() as db:
        context = build_context(db, resource, scope_id)
        if context is None:
            return {"status": "not_found", "detail": _DETAIL_BY_RESOURCE[resource]}
        strategy_id = context["strategy_id"]
        model = get_settings().copilot_model
        provider = get_provider()
        if not provider.enabled:
            return _record_insight(
                db,
                strategy_id,
                status=CopilotInsightStatus.FAILED,
                model=model,
                error="模型未启用:未配置 STREET_DEEPSEEK_API_KEY",
                duration_ms=0,
            )
        started = time.monotonic()
        try:
            narrative = provider.synthesize(context)
        except CopilotProviderError as exc:
            return _record_insight(
                db,
                strategy_id,
                status=CopilotInsightStatus.FAILED,
                model=model,
                error=str(exc)[:_MAX_ERROR_CHARS],
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        text = narrative.strip() if narrative else ""
        if not text:
            return _record_insight(
                db,
                strategy_id,
                status=CopilotInsightStatus.FAILED,
                model=model,
                error="模型未返回叙述",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        return _record_insight(
            db,
            strategy_id,
            status=CopilotInsightStatus.DONE,
            model=model,
            narrative=text,
            duration_ms=int((time.monotonic() - started) * 1000),
        )


@celery_app.task(name="copilot.synthesize")
def run_synthesize_task(resource: str, resource_id: str) -> dict:
    return execute_synthesize(resource, resource_id)


def execute_suggest(resource: str, resource_id: str) -> dict:
    """Pick one deterministic suggestion card via the provider + record it.

    The deterministic derivation (``derive_suggestions``) is the executable
    truth; the model only ranks within it. Records exactly one row in
    ``copilot_suggestions`` — DONE with the pick, or FAILED when the provider
    is disabled / errored / replied with an out-of-set pick / there is nothing
    to suggest.
    """
    try:
        scope_id = UUID(resource_id)
    except (ValueError, AttributeError):
        return {"status": "not_found", "detail": _DETAIL_BY_RESOURCE[resource]}
    with _tasks.SessionLocal() as db:
        context = build_context(db, resource, scope_id)
        if context is None:
            return {"status": "not_found", "detail": _DETAIL_BY_RESOURCE[resource]}
        strategy_id = context["strategy_id"]
        model = get_settings().copilot_model
        provider = get_provider()
        if not provider.enabled:
            return _record_suggestion(
                db,
                strategy_id,
                status=CopilotSuggestionStatus.FAILED,
                model=model,
                error="模型未启用:未配置 STREET_DEEPSEEK_API_KEY",
                duration_ms=0,
            )
        candidates = derive_suggestions(db, strategy_id)
        if not candidates:
            return _record_suggestion(
                db,
                strategy_id,
                status=CopilotSuggestionStatus.FAILED,
                model=model,
                error="当前没有可建议的动作",
                duration_ms=0,
            )
        started = time.monotonic()
        try:
            pick = provider.suggest(context, candidates)
        except CopilotProviderError as exc:
            return _record_suggestion(
                db,
                strategy_id,
                status=CopilotSuggestionStatus.FAILED,
                model=model,
                error=str(exc)[:_MAX_ERROR_CHARS],
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        picked_id = pick.get("picked_id") if pick else None
        reason = pick.get("reason", "") if pick else ""
        allowed = {c.get("key") for c in candidates}
        if not picked_id or picked_id not in allowed:
            return _record_suggestion(
                db,
                strategy_id,
                status=CopilotSuggestionStatus.FAILED,
                model=model,
                error="模型未返回候选内的建议",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        return _record_suggestion(
            db,
            strategy_id,
            status=CopilotSuggestionStatus.DONE,
            model=model,
            picked_id=picked_id,
            reason=reason,
            duration_ms=int((time.monotonic() - started) * 1000),
        )


@celery_app.task(name="copilot.suggest")
def run_suggest_task(resource: str, resource_id: str) -> dict:
    return execute_suggest(resource, resource_id)
