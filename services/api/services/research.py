from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.models import (
    Backtest,
    ResearchExport,
    ResearchNote,
    Strategy,
    StrategyVersion,
    ValidationRun,
)
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


def _assert_validation_run(db: Session, strategy_id: UUID, run_id: UUID | None) -> None:
    if run_id is None:
        return
    run = db.get(ValidationRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="验证运行不存在")
    if run.strategy_id != strategy_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="验证运行不属于该策略")


def resolve_note_evidence(db: Session, note: ResearchNote) -> dict:
    """P2.4 证据清单：从关联的版本/回测/验证运行解析出可供第三人回溯的输入结果。"""
    items: list[dict] = []
    version = (
        db.get(StrategyVersion, note.strategy_version_id) if note.strategy_version_id else None
    )
    strategy = db.get(Strategy, note.strategy_id)
    if version is not None:
        items.append(
            {
                "kind": "version",
                "id": str(version.id),
                "label": f"{strategy.name if strategy else '策略'} v{version.version}",
                "version": version.version,
                "config_digest": None,
            }
        )
    if note.backtest_id is not None:
        backtest = db.get(Backtest, note.backtest_id)
        if backtest is not None:
            items.append(
                {
                    "kind": "backtest",
                    "id": str(backtest.id),
                    "label": f"{backtest.start_date} → {backtest.end_date} · {backtest.benchmark}",
                    "status": backtest.status.value,
                    "engine_version": backtest.engine_version,
                    "data_version": backtest.data_version,
                    "benchmark": backtest.benchmark,
                    "start_date": backtest.start_date.isoformat(),
                    "end_date": backtest.end_date.isoformat(),
                }
            )
    if note.validation_run_id is not None:
        run = db.get(ValidationRun, note.validation_run_id)
        if run is not None:
            items.append(
                {
                    "kind": "validation",
                    "id": str(run.id),
                    "label": f"{run.kind.value} 验证",
                    "status": run.status.value,
                    "backtest_id": str(run.backtest_id) if run.backtest_id else None,
                }
            )
    from datetime import datetime, timezone

    return {"items": items, "captured_at": datetime.now(timezone.utc).isoformat()}


def export_note(db: Session, note_id: UUID) -> ResearchExport:
    """P2.4 冻结导出：把当前笔记与解析后的证据清单固化为不可变行，
    之后的编辑不会悄悄改写这份导出（新导出另起一行）。"""
    note = get_note(db, note_id)
    payload = {
        "note": {
            "note_id": str(note.id),
            "title": note.title,
            "hypothesis": note.hypothesis,
            "method": note.method,
            "conclusion": note.conclusion,
            "failure_modes": note.failure_modes,
            "drafted_by": note.drafted_by or {},
        },
        "manifest": {
            "strategy_id": str(note.strategy_id),
            "strategy_version_id": str(note.strategy_version_id)
            if note.strategy_version_id
            else None,
            "backtest_id": str(note.backtest_id) if note.backtest_id else None,
            "validation_run_id": str(note.validation_run_id) if note.validation_run_id else None,
        },
        "evidence": resolve_note_evidence(db, note),
    }
    export = ResearchExport(note_id=note.id, payload=payload)
    db.add(export)
    db.commit()
    db.refresh(export)
    return export


def list_exports(db: Session, note_id: UUID) -> list[ResearchExport]:
    get_note(db, note_id)
    return list(
        db.scalars(
            select(ResearchExport)
            .where(ResearchExport.note_id == note_id)
            .order_by(ResearchExport.created_at.desc())
        ).all()
    )


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
    _assert_validation_run(db, strategy.id, payload.validation_run_id)
    note = ResearchNote(
        strategy_id=strategy.id,
        strategy_version_id=payload.strategy_version_id,
        backtest_id=payload.backtest_id,
        validation_run_id=payload.validation_run_id,
        title=_clean_title(title),
        hypothesis=_text(hypothesis),
        method=_text(payload.method),
        conclusion=_text(payload.conclusion),
        failure_modes=_text(payload.failure_modes),
        evidence=dict(payload.evidence or {})
        if payload.strategy_version_id or payload.backtest_id or payload.validation_run_id
        else {},
        drafted_by=dict(payload.drafted_by or {}),
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
    if "validation_run_id" in data:
        _assert_validation_run(db, note.strategy_id, data["validation_run_id"])
        note.validation_run_id = data["validation_run_id"]
    if "evidence" in data and data["evidence"] is not None:
        note.evidence = dict(data["evidence"])
    if "drafted_by" in data and data["drafted_by"] is not None:
        note.drafted_by = dict(data["drafted_by"])
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
