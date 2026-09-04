from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.schemas import (
    ResearchNoteCreate,
    ResearchNoteOut,
    ResearchNotePage,
    ResearchNoteUpdate,
)
from services.api.services import research as research_service

router = APIRouter(prefix="/research-notes", tags=["research"])


@router.get("", response_model=ResearchNotePage)
def list_notes(
    db: Session = Depends(get_db),
    strategy_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ResearchNotePage:
    rows, total = research_service.list_notes(
        db, strategy_id=strategy_id, limit=limit, offset=offset
    )
    return ResearchNotePage(
        items=[ResearchNoteOut.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ResearchNoteOut, status_code=status.HTTP_201_CREATED)
def create_note(payload: ResearchNoteCreate, db: Session = Depends(get_db)) -> ResearchNoteOut:
    return ResearchNoteOut.model_validate(research_service.create_note(db, payload))


@router.get("/{note_id}", response_model=ResearchNoteOut)
def get_note(note_id: UUID, db: Session = Depends(get_db)) -> ResearchNoteOut:
    return ResearchNoteOut.model_validate(research_service.get_note(db, note_id))


@router.patch("/{note_id}", response_model=ResearchNoteOut)
def update_note(
    note_id: UUID, payload: ResearchNoteUpdate, db: Session = Depends(get_db)
) -> ResearchNoteOut:
    return ResearchNoteOut.model_validate(research_service.update_note(db, note_id, payload))


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: UUID, db: Session = Depends(get_db)) -> Response:
    research_service.delete_note(db, note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
