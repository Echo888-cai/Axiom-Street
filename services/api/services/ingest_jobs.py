"""Celery-backed market data ingest jobs with progress."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from quant.data.ingest_spy import data_status, ingest
from quant.data.symbols import normalize_symbols
from quant.data.types import DataQualityError, ProviderCapabilityError
from services.api import db as db_module
from services.api.models import IngestJob, IngestJobStatus
from services.api.services import snapshots as snapshot_service
from services.api.settings import get_settings


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
