"""Unified task center (P2.2): read model + cancel delegation.

Contract: GET /api/v1/tasks, GET /api/v1/tasks/{id}, POST /api/v1/tasks/{id}/cancel.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.schemas import TaskOut
from services.api.services import tasks as tasks_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
def list_tasks(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[TaskOut]:
    """Newest-first unified task list (backtests, validation, ingest, copilot)."""
    return tasks_service.list_tasks(db, limit=limit)


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: UUID, db: Session = Depends(get_db)) -> TaskOut:
    task = tasks_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="任务不存在。")
    return task


@router.post("/{task_id}/cancel", response_model=TaskOut)
def cancel_task(task_id: UUID, db: Session = Depends(get_db)) -> TaskOut:
    return tasks_service.cancel_task(db, task_id)
