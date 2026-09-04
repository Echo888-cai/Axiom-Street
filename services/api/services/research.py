from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.models import Backtest, ResearchNote, Strategy, StrategyVersion
from services.api.schemas import ResearchNoteCreate, ResearchNoteUpdate
from services.api.services.strategies import get_strategy, latest_version


def _clean_title(value: str | None) -> str:
    title = (value or "").strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标题不能为空")
    if len(title) > 255:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标题过长")
    return title


def _text(value: str | None) -> str:
    return value if value is not None else ""


def _assert_version(db: Session, strategy_id: UUID, version_id: UUID | None) -> None:
    if version_id is None:
        return
    version = db.get(StrategyVersion, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="策略版本不存在")
    if version.strategy_id != strategy_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="版本不属于该策略")


def _assert_backtest(db: Session, strategy_id: UUID, backtest_id: UUID | None) -> None:
    if backtest_id is None:
        return
    backtest = db.get(Backtest, backtest_id)
    if not backtest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回测不存在")
    version = db.get(StrategyVersion, backtest.strategy_version_id)
    if version is None or version.strategy_id != strategy_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="回测不属于该策略")


def _hypothesis_from_strategy(db: Session, strategy: Strategy) -> str:
    version = latest_version(db, strategy.id)
    if not version or not isinstance(version.config, dict):
        return ""
    raw = version.config.get("hypothesis")
    return raw.strip() if isinstance(raw, str) else ""


def list_notes(
    db: Session,
    *,
    strategy_id: UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[ResearchNote], int]:
    stmt = select(ResearchNote)
    count_stmt = select(func.count()).select_from(ResearchNote)
    if strategy_id is not None:
        get_strategy(db, strategy_id)
        stmt = stmt.where(ResearchNote.strategy_id == strategy_id)
        count_stmt = count_stmt.where(ResearchNote.strategy_id == strategy_id)
    total = int(db.scalar(count_stmt) or 0)
    rows = list(
        db.scalars(stmt.order_by(ResearchNote.updated_at.desc()).offset(offset).limit(limit)).all()
    )
    return rows, total


def get_note(db: Session, note_id: UUID) -> ResearchNote:
    note = db.get(ResearchNote, note_id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究笔记不存在")
    return note


def create_note(db: Session, payload: ResearchNoteCreate) -> ResearchNote:
    strategy = get_strategy(db, payload.strategy_id)
    _assert_version(db, strategy.id, payload.strategy_version_id)
    _assert_backtest(db, strategy.id, payload.backtest_id)
    title = (payload.title or "").strip() or f"{strategy.name} 研究笔记"
    hypothesis = payload.hypothesis
    if hypothesis is None:
        hypothesis = _hypothesis_from_strategy(db, strategy)
    note = ResearchNote(
        strategy_id=strategy.id,
        strategy_version_id=payload.strategy_version_id,
        backtest_id=payload.backtest_id,
        title=_clean_title(title),
        hypothesis=_text(hypothesis),
        method=_text(payload.method),
        conclusion=_text(payload.conclusion),
        failure_modes=_text(payload.failure_modes),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def update_note(db: Session, note_id: UUID, payload: ResearchNoteUpdate) -> ResearchNote:
    note = get_note(db, note_id)
    data = payload.model_dump(exclude_unset=True)
    if "strategy_version_id" in data:
        _assert_version(db, note.strategy_id, data["strategy_version_id"])
        note.strategy_version_id = data["strategy_version_id"]
    if "backtest_id" in data:
        _assert_backtest(db, note.strategy_id, data["backtest_id"])
        note.backtest_id = data["backtest_id"]
    if "title" in data:
        note.title = _clean_title(data["title"])
    if "hypothesis" in data:
        note.hypothesis = _text(data["hypothesis"])
    if "method" in data:
        note.method = _text(data["method"])
    if "conclusion" in data:
        note.conclusion = _text(data["conclusion"])
    if "failure_modes" in data:
        note.failure_modes = _text(data["failure_modes"])
    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, note_id: UUID) -> None:
    note = get_note(db, note_id)
    db.delete(note)
    db.commit()
