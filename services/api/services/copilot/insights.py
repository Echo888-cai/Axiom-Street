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

from services.api.models import CopilotInsight


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
