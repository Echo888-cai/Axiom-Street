"""Read-only insight ledger queries for the copilot panel (P5-2).

Same isolation as ``context.py``: reads only, column-level outbound boundary
included. Rows are written exclusively by the worker synthesize task
(``services/worker/tasks/copilot.py``); nothing here ever writes.
"""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.models import CopilotChatMessage, CopilotInsight, CopilotSuggestion


def list_insights(db: Session, strategy_id: UUID, limit: int = 10) -> list[dict]:
    rows = db.execute(
        select(CopilotInsight)
        .where(CopilotInsight.strategy_id == strategy_id)
        .order_by(CopilotInsight.created_at.desc(), CopilotInsight.id.desc())
        .limit(limit)
    ).scalars()
    return [
        {
            "id": row.id,
            "strategy_id": row.strategy_id,
            "status": row.status.value if isinstance(row.status, Enum) else row.status,
            "model": row.model,
            "narrative": row.narrative or "",
            "error": row.error,
            "duration_ms": row.duration_ms,
            "created_at": row.created_at,
            "finished_at": row.finished_at,
        }
        for row in rows
    ]


def latest_suggestion(db: Session, strategy_id: UUID) -> dict | None:
    """Newest model priority pick for a strategy (P5-3), or None."""
    row = (
        db.execute(
            select(CopilotSuggestion)
            .where(CopilotSuggestion.strategy_id == strategy_id)
            .order_by(CopilotSuggestion.created_at.desc(), CopilotSuggestion.id.desc())
        )
        .scalars()
        .first()
    )
    if row is None:
        return None
    return {
        "id": row.id,
        "strategy_id": row.strategy_id,
        "status": row.status.value if isinstance(row.status, Enum) else row.status,
        "model": row.model,
        "picked_id": row.picked_id,
        "reason": row.reason or "",
        "error": row.error,
        "duration_ms": row.duration_ms,
        "created_at": row.created_at,
        "finished_at": row.finished_at,
    }


def list_chat_messages(db: Session, strategy_id: UUID, limit: int = 30) -> list[dict]:
    """Return recent scoped chat turns newest first."""
    rows = db.execute(
        select(CopilotChatMessage)
        .where(CopilotChatMessage.strategy_id == strategy_id)
        .order_by(CopilotChatMessage.created_at.desc(), CopilotChatMessage.id.desc())
        .limit(limit)
    ).scalars()
    return [
        {
            "id": row.id,
            "strategy_id": row.strategy_id,
            "resource": row.resource,
            "resource_id": row.resource_id,
            "user_message": row.user_message,
            "assistant_message": row.assistant_message,
            "status": row.status.value if isinstance(row.status, Enum) else row.status,
            "model": row.model,
            "error": row.error,
            "duration_ms": row.duration_ms,
            "created_at": row.created_at,
            "finished_at": row.finished_at,
        }
        for row in rows
    ]
