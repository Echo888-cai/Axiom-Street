from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from quant.data.ingest_spy import data_status
from quant.data.symbols import normalize_symbols
from services.api.db import SessionLocal, get_db
from services.api.health import docker_status
from services.api.models import DataSnapshot
from services.api.services import ingest_jobs as ingest_job_service
from services.api.settings import get_settings

router = APIRouter(prefix="/data", tags=["data"])


class IngestRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["SPY"])
    start: str = "2010-01-01"
    end: Optional[str] = None
    provider: str = Field(default="auto", description="auto | yfinance | stooq | polygon")
    convert_lean: bool = True
    mode: str = Field(default="full", description="full | incremental")
    reconcile_with: Optional[str] = Field(
        default=None,
        description="optional secondary provider for dual-source reconciliation",
    )


def _lean_engine_status() -> dict:
    docker = docker_status()
    return {
        "engine": "lean",
        "image": docker.get("image"),
        "docker_available": bool(docker.get("ok")),
        "source": docker.get("source"),
        "reported_at": docker.get("reported_at"),
        "note": docker.get("note"),
    }


def _create_job(payload: IngestRequest, db: Session) -> dict:
    try:
        tickers = normalize_symbols(payload.symbols)
        job = ingest_job_service.create_ingest_job(
            db,
            symbols=tickers,
            start=payload.start,
            end=payload.end,
            provider=payload.provider,
            mode=payload.mode,
            reconcile_with=payload.reconcile_with,
            convert_lean=payload.convert_lean,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ingest_job_service.serialize_job(job)


@router.get("/status")
def get_data_status() -> dict:
    settings = get_settings()
    status_payload = data_status(Path(settings.data_root))
    status_payload["lean_engine"] = _lean_engine_status()
    return status_payload


@router.get("/snapshots")
def list_snapshots(db: Session = Depends(get_db)) -> dict:
    rows = list(db.scalars(select(DataSnapshot).order_by(DataSnapshot.created_at.desc())).all())
    return {
        "total": len(rows),
        "items": [
            {
                "id": str(row.id),
                "snapshot_key": row.snapshot_key,
                "symbols": row.symbols,
                "provider": row.provider,
                "row_count": row.row_count,
                "content_sha256": row.content_sha256,
                "corporate_actions_verified": row.corporate_actions_verified,
                "superseded_by": str(row.superseded_by) if row.superseded_by else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
def ingest_endpoint(payload: IngestRequest, db: Session = Depends(get_db)) -> dict:
    """Enqueue an ingest job. Returns immediately with job id + progress fields."""
    return _create_job(payload, db)


@router.post("/ingest/spy", status_code=status.HTTP_202_ACCEPTED)
def ingest_spy_endpoint(payload: IngestRequest, db: Session = Depends(get_db)) -> dict:
    payload.symbols = ["SPY"]
    return _create_job(payload, db)


@router.get("/ingest/{job_id}")
def get_ingest_job(job_id: UUID, db: Session = Depends(get_db)) -> dict:
    try:
        job = ingest_job_service.get_job(db, job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ingest_job_service.serialize_job(job)


@router.get("/ingest/{job_id}/events")
async def ingest_job_events(job_id: UUID) -> EventSourceResponse:
    async def event_generator():
        terminal = {"COMPLETED", "FAILED", "CANCELLED"}
        while True:
            db = SessionLocal()
            try:
                try:
                    job = ingest_job_service.get_job(db, job_id)
                except KeyError:
                    yield {
                        "event": "done",
                        "data": json.dumps({"id": str(job_id), "status": "FAILED", "error": "not_found"}),
                    }
                    break
                payload = ingest_job_service.serialize_job(job)
                yield {"event": "progress", "data": json.dumps(payload)}
                if payload["status"] in terminal:
                    yield {"event": "done", "data": json.dumps(payload)}
                    break
            finally:
                db.close()
            await asyncio.sleep(1.0)

    return EventSourceResponse(event_generator())
