"""Unified task read model (P2.2): aggregates backtests, validation runs,
ingest jobs and copilot insights into one shape the task drawer consumes.

This is a projection over the existing execution ledgers — it never enqueues,
never second-guesses the workers, and cancel only delegates to capabilities
that already exist (backtests today).
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.models import (
    Backtest,
    BacktestStatus,
    CopilotInsight,
    IngestJob,
    Strategy,
    StrategyVersion,
    ValidationRun,
)
from services.api.schemas import TaskOut

_KIND_BACKTEST = "backtest"
_KIND_VALIDATION = "validation"
_KIND_INGEST = "ingest"
_KIND_COPILOT = "copilot"

_TERMINAL = frozenset({BacktestStatus.COMPLETED, BacktestStatus.FAILED, BacktestStatus.CANCELLED})


def _backtest_task(backtest: Backtest, strategy_name: str | None) -> TaskOut:
    window = f"{backtest.start_date} → {backtest.end_date}"
    return TaskOut(
        id=backtest.id,
        kind=_KIND_BACKTEST,
        title=f"{strategy_name or '策略'} · {window}",
        status=backtest.status.value,
        progress_step=backtest.progress_step,
        created_at=backtest.created_at,
        finished_at=backtest.finished_at,
        ref=f"/backtests/{backtest.id}",
        strategy_name=strategy_name,
        cancelable=True,
    )


def _validation_task(run: ValidationRun) -> TaskOut:
    return TaskOut(
        id=run.id,
        kind=_KIND_VALIDATION,
        title=f"{run.kind.value} 验证",
        status=run.status.value,
        progress_step=run.progress_step,
        created_at=run.created_at,
        finished_at=run.finished_at,
        ref="/validation",
        cancelable=False,
    )


def _ingest_task(job: IngestJob) -> TaskOut:
    raw: list[Any] = cast("list[Any]", job.symbols) if isinstance(job.symbols, list) else []
    symbols: list[str] = [str(s) for s in raw]
    title = f"摄取 {', '.join(symbols[:5]) or job.id}" + (f"（{job.mode}）" if job.mode else "")
    return TaskOut(
        id=job.id,
        kind=_KIND_INGEST,
        title=title,
        status=job.status.value,
        progress_step=job.progress_step,
        created_at=job.created_at,
        finished_at=job.finished_at,
        ref="/settings",
        cancelable=False,
    )


def _copilot_task(insight: CopilotInsight) -> TaskOut:
    return TaskOut(
        id=insight.id,
        kind=_KIND_COPILOT,
        title="研究助手 · 策略摘要",
        status=insight.status.value,
        progress_step=None,
        created_at=insight.created_at,
        finished_at=None,
        ref=f"/strategies/{insight.strategy_id}" if insight.strategy_id else "/settings",
        cancelable=False,
    )


def list_tasks(db: Session, limit: int = 50) -> list[TaskOut]:
    """Newest-first projection across the four execution ledgers."""
    tasks: list[TaskOut] = []

    backtest_rows = db.execute(
        select(Backtest, Strategy.name)
        .join(StrategyVersion, Backtest.strategy_version_id == StrategyVersion.id)
        .join(Strategy, StrategyVersion.strategy_id == Strategy.id)
        .order_by(Backtest.created_at.desc())
        .limit(limit)
    ).all()
    tasks.extend(_backtest_task(b, name) for b, name in backtest_rows)

    runs = db.scalars(
        select(ValidationRun).order_by(ValidationRun.created_at.desc()).limit(limit)
    ).all()
    tasks.extend(_validation_task(r) for r in runs)

    jobs = db.scalars(select(IngestJob).order_by(IngestJob.created_at.desc()).limit(limit)).all()
    tasks.extend(_ingest_task(j) for j in jobs)

    insights = db.scalars(
        select(CopilotInsight).order_by(CopilotInsight.created_at.desc()).limit(limit)
    ).all()
    tasks.extend(_copilot_task(i) for i in insights)

    tasks.sort(key=lambda t: t.created_at, reverse=True)
    return tasks[:limit]


def get_task(db: Session, task_id: UUID) -> TaskOut | None:
    backtest = db.get(Backtest, task_id)
    if backtest is not None:
        version = db.get(StrategyVersion, backtest.strategy_version_id)
        strategy = db.get(Strategy, version.strategy_id) if version else None
        return _backtest_task(backtest, strategy.name if strategy else None)
    run = db.get(ValidationRun, task_id)
    if run is not None:
        return _validation_task(run)
    job = db.get(IngestJob, task_id)
    if job is not None:
        return _ingest_task(job)
    insight = db.get(CopilotInsight, task_id)
    if insight is not None:
        return _copilot_task(insight)
    return None


def cancel_task(db: Session, task_id: UUID) -> TaskOut:
    """Cancel by delegating to the underlying capability; semantics stay explicit."""
    backtest = db.get(Backtest, task_id)
    if backtest is not None:
        if backtest.status in _TERMINAL:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"任务已结束（{backtest.status.value}），无需取消。",
            )
        from services.api.services.backtests import cancel_backtest

        cancel_backtest(db, task_id)
        return get_task(db, task_id)  # type: ignore[return-value]

    for _kind, row in (
        (ValidationRun, db.get(ValidationRun, task_id)),
        (IngestJob, db.get(IngestJob, task_id)),
        (CopilotInsight, db.get(CopilotInsight, task_id)),
    ):
        if row is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该类型任务暂不支持取消：只有回测可在排队/运行中取消。",
            )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在。")
