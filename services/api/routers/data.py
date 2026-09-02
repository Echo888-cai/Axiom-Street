from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from quant.data.ingest_spy import data_status, ingest
from quant.data.symbols import normalize_symbols
from quant.data.types import DataQualityError, ProviderCapabilityError
from services.api.db import get_db
from services.api.health import docker_status
from services.api.models import DataSnapshot
from services.api.services import snapshots as snapshot_service
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


def _run_ingest(payload: IngestRequest, db: Session) -> dict:
    settings = get_settings()
    try:
        tickers = normalize_symbols(payload.symbols)
        result = ingest(
            symbols=tickers,
            data_root=Path(settings.data_root),
            start=payload.start,
            end=payload.end,
            provider=payload.provider,
            convert_lean=payload.convert_lean,
            mode=payload.mode,
            reconcile_with=payload.reconcile_with,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DataQualityError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "data_quality", "message": str(exc), "report": exc.report},
        ) from exc
    except ProviderCapabilityError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "provider_capability", "message": str(exc)},
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    snapshot = snapshot_service.upsert_snapshot_from_ingest(db, result)
    db.commit()
    parquet = result.get("parquet")
    return {
        "ok": True,
        "parquet": str(parquet) if parquet is not None else None,
        "snapshot_key": result.get("snapshot_key"),
        "data_snapshot_id": str(snapshot.id),
        "symbols": result.get("symbols") or tickers,
        "quality_report": result.get("quality_report"),
        "ingest_mode": result.get("ingest_mode") or payload.mode,
        "fetch_windows": result.get("fetch_windows"),
        "prior_snapshot_key": result.get("prior_snapshot_key"),
        "reconcile_with": result.get("reconcile_with"),
        "reconcile_reports": result.get("reconcile_reports"),
        "status": data_status(Path(settings.data_root)),
    }


@router.get("/status")
def get_data_status() -> dict:
    settings = get_settings()
    status = data_status(Path(settings.data_root))
    status["lean_engine"] = _lean_engine_status()
    return status


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


@router.post("/ingest")
def ingest_endpoint(payload: IngestRequest, db: Session = Depends(get_db)) -> dict:
    return _run_ingest(payload, db)


@router.post("/ingest/spy")
def ingest_spy_endpoint(payload: IngestRequest, db: Session = Depends(get_db)) -> dict:
    payload.symbols = ["SPY"]
    return _run_ingest(payload, db)
