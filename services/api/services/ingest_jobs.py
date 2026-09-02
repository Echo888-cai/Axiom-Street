"""Celery-backed market data ingest jobs with progress."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant.data.ingest_spy import data_status, ingest
from quant.data.symbols import normalize_symbols
from quant.data.types import DataQualityError, ProviderCapabilityError
from services.api import db as db_module
from services.api.models import IngestJob, IngestJobStatus
from services.api.services import snapshots as snapshot_service
from services.api.settings import get_settings

ACTIVE_INGEST_STATUSES = (
    IngestJobStatus.QUEUED,
    IngestJobStatus.STARTING,
    IngestJobStatus.RUNNING,
)

_SKIP_MESSAGES = {
    "disabled": "定时全量校验已关闭（STREET_MARKET_RECONCILE_ENABLED=false）",
    "no_symbols": "还没有行情快照，无法做全量校验。请先拉取至少一只标的。",
    "ingest_in_progress": "已有行情任务在跑，跳过本次全量校验以免并发写快照。",
}


def serialize_job(job: IngestJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "status": job.status.value if isinstance(job.status, IngestJobStatus) else str(job.status),
        "progress_step": job.progress_step,
        "symbols": list(job.symbols or []),
        "start": job.start,
        "end": job.end,
        "provider": job.provider,
        "mode": job.mode,
        "reconcile_with": job.reconcile_with,
        "convert_lean": bool(job.convert_lean),
        "current_symbol": job.current_symbol,
        "completed_symbols": int(job.completed_symbols or 0),
        "total_symbols": int(job.total_symbols or 0),
        "result": job.result,
        "error": job.error,
        "data_snapshot_id": str(job.data_snapshot_id) if job.data_snapshot_id else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


def create_ingest_job(
    db: Session,
    *,
    symbols: list[str],
    start: str = "2010-01-01",
    end: str | None = None,
    provider: str = "auto",
    mode: str = "full",
    reconcile_with: str | None = None,
    convert_lean: bool = True,
) -> IngestJob:
    tickers = normalize_symbols(symbols)
    job = IngestJob(
        status=IngestJobStatus.QUEUED,
        progress_step="Queued",
        symbols=tickers,
        start=start,
        end=end,
        provider=provider,
        mode=mode,
        reconcile_with=reconcile_with,
        convert_lean=convert_lean,
        total_symbols=len(tickers),
        completed_symbols=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = str(job.id)
    _enqueue(job_id)
    # Sync path mutates the row in another session; reload before returning.
    db.expire(job)
    db.refresh(job)
    return job


def _enqueue(job_id: str) -> None:
    settings = get_settings()
    if settings.sync_ingests:
        execute_ingest_job(job_id)
        return
    from services.worker.tasks import run_ingest_task

    run_ingest_task.delay(job_id)


def get_job(db: Session, job_id: UUID) -> IngestJob:
    job = db.get(IngestJob, job_id)
    if job is None:
        raise KeyError(f"ingest job {job_id} not found")
    return job


def execute_ingest_job(job_id: str) -> dict[str, Any]:
    settings = get_settings()
    # Resolve SessionLocal at call time so tests can swap the engine.
    db = db_module.SessionLocal()
    try:
        job = db.get(IngestJob, UUID(job_id))
        if job is None:
            return {"ok": False, "error": "not_found"}

        now = datetime.now(timezone.utc)
        job.status = IngestJobStatus.STARTING
        job.progress_step = "Starting"
        job.started_at = now
        job.error = None
        db.commit()

        def on_progress(symbol: str, index: int, total: int) -> None:
            job.status = IngestJobStatus.RUNNING
            job.current_symbol = symbol
            job.completed_symbols = max(0, index - 1)
            job.total_symbols = total
            job.progress_step = f"Fetching {symbol} ({index}/{total})"
            db.commit()

        job.status = IngestJobStatus.RUNNING
        job.progress_step = "Running"
        db.commit()

        try:
            result = ingest(
                symbols=list(job.symbols or []),
                data_root=Path(settings.data_root),
                start=job.start,
                end=job.end,
                provider=job.provider,
                convert_lean=bool(job.convert_lean),
                mode=job.mode,
                reconcile_with=job.reconcile_with,
                on_progress=on_progress,
            )
        except DataQualityError as exc:
            job.status = IngestJobStatus.FAILED
            job.finished_at = datetime.now(timezone.utc)
            job.progress_step = "Failed"
            job.error = {"code": "data_quality", "message": str(exc), "report": exc.report}
            db.commit()
            return {"ok": False, "error": job.error}
        except ProviderCapabilityError as exc:
            job.status = IngestJobStatus.FAILED
            job.finished_at = datetime.now(timezone.utc)
            job.progress_step = "Failed"
            job.error = {"code": "provider_capability", "message": str(exc)}
            db.commit()
            return {"ok": False, "error": job.error}
        except Exception as exc:  # noqa: BLE001 — persist fail-loud payload for UI
            job.status = IngestJobStatus.FAILED
            job.finished_at = datetime.now(timezone.utc)
            job.progress_step = "Failed"
            job.error = {"code": "ingest_failed", "message": str(exc)}
            db.commit()
            return {"ok": False, "error": job.error}

        job.progress_step = "Writing snapshot"
        db.commit()
        snapshot = snapshot_service.upsert_snapshot_from_ingest(db, result)
        parquet = result.get("parquet")
        payload = {
            "ok": True,
            "parquet": str(parquet) if parquet is not None else None,
            "snapshot_key": result.get("snapshot_key"),
            "data_snapshot_id": str(snapshot.id),
            "symbols": result.get("symbols") or list(job.symbols or []),
            "quality_report": result.get("quality_report"),
            "ingest_mode": result.get("ingest_mode") or job.mode,
            "fetch_windows": result.get("fetch_windows"),
            "prior_snapshot_key": result.get("prior_snapshot_key"),
            "reconcile_with": result.get("reconcile_with"),
            "reconcile_reports": result.get("reconcile_reports"),
            "status": data_status(Path(settings.data_root)),
        }
        job.status = IngestJobStatus.COMPLETED
        job.finished_at = datetime.now(timezone.utc)
        job.progress_step = "Completed"
        job.current_symbol = None
        job.completed_symbols = int(job.total_symbols or 0)
        job.data_snapshot_id = snapshot.id
        job.result = payload
        job.error = None
        db.commit()
        return payload
    finally:
        db.close()


def latest_ingest_job(db: Session) -> IngestJob | None:
    return db.scalars(
        select(IngestJob).order_by(
            IngestJob.created_at.desc(),
            IngestJob.started_at.desc(),
        )
    ).first()


def has_active_ingest_job(db: Session) -> IngestJob | None:
    return db.scalars(
        select(IngestJob)
        .where(IngestJob.status.in_(ACTIVE_INGEST_STATUSES))
        .order_by(IngestJob.created_at.desc())
    ).first()


def _skip(reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "skipped": True,
        "reason": reason,
        "message": _SKIP_MESSAGES[reason],
    }
    payload.update(extra)
    return payload


def schedule_market_reconcile(
    db: Session | None = None,
    *,
    force: bool = False,
    scheduled: bool = False,
) -> dict[str, Any]:
    """Enqueue a full re-pull of the latest snapshot universe to catch vendor revisions.

    Creates an ``IngestJob`` with ``mode=full`` so progress/SSE stay consistent with
    manual Settings pulls. Beat calls this with ``scheduled=True`` (honours the
    enabled flag). The HTTP endpoint always allows a manual run unless another
    ingest is already active (``force`` overrides that guard).
    """
    settings = get_settings()
    owns_session = db is None
    session = db or db_module.SessionLocal()
    try:
        if scheduled and not settings.market_reconcile_enabled and not force:
            return _skip("disabled")

        status = data_status(Path(settings.data_root))
        symbols = list(status.get("symbols") or [])
        if not symbols:
            return _skip("no_symbols")

        active = has_active_ingest_job(session)
        if active is not None and not force:
            return _skip("ingest_in_progress", active_job_id=str(active.id))

        secondary = (settings.market_reconcile_with or "").strip() or None
        job = create_ingest_job(
            session,
            symbols=symbols,
            start="2010-01-01",
            end=None,
            provider=(settings.market_reconcile_provider or "auto").strip() or "auto",
            mode="full",
            reconcile_with=secondary,
            convert_lean=True,
        )
        return {
            "ok": True,
            "skipped": False,
            "job": serialize_job(job),
            "symbols": list(job.symbols or []),
        }
    finally:
        if owns_session:
            session.close()
