from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.schemas import (
    ResearchExportOut,
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


@router.get("/{note_id}/evidence")
def note_evidence(note_id: UUID, db: Session = Depends(get_db)) -> dict:
    """P2.4 证据清单：第三人可凭此回溯版本/回测/验证的输入结果。"""
    note = research_service.get_note(db, note_id)
    return research_service.resolve_note_evidence(db, note)


@router.post(
    "/{note_id}/export", response_model=ResearchExportOut, status_code=status.HTTP_201_CREATED
)
def export_note(note_id: UUID, db: Session = Depends(get_db)) -> ResearchExportOut:
    """P2.4 冻结导出：导出时刻的证据清单与时间固定，之后的编辑不改写旧导出。"""
    export = research_service.export_note(db, note_id)
    return ResearchExportOut(
        id=export.id,
        note_id=export.note_id,
        created_at=export.created_at,
        payload=export.payload,
    )


@router.get("/{note_id}/exports", response_model=list[ResearchExportOut])
def list_exports(note_id: UUID, db: Session = Depends(get_db)) -> list[ResearchExportOut]:
    return [
        ResearchExportOut(
            id=export.id,
            note_id=export.note_id,
            created_at=export.created_at,
            payload=export.payload,
        )
        for export in research_service.list_exports(db, note_id)
    ]
