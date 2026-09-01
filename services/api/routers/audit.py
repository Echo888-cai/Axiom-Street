from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.models import AuditLog
from services.api.schemas import AuditLogOut, AuditLogPage

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=AuditLogPage)
def list_audit_logs(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    object_type: str | None = None,
    object_id: str | None = None,
    action: str | None = None,
) -> AuditLogPage:
    filters = []
    if object_type:
        filters.append(AuditLog.object_type == object_type)
    if object_id:
        filters.append(AuditLog.object_id == object_id)
    if action:
        filters.append(AuditLog.action == action)
    total = int(db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0)
    rows = list(
        db.scalars(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.timestamp.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return AuditLogPage(
        items=[AuditLogOut.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
