from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from quant.data.ingest_spy import data_status, ingest_spy
from quant.data.types import DataQualityError, ProviderCapabilityError
from quant.engine.lean import LeanQuantEngine
from services.api.db import get_db
from services.api.services import snapshots as snapshot_service
from services.api.settings import get_settings

router = APIRouter(prefix="/data", tags=["data"])


class IngestRequest(BaseModel):
    start: str = "2010-01-01"
    end: Optional[str] = None
    provider: str = Field(default="auto", description="auto | yfinance | stooq")
    convert_lean: bool = True


@router.get("/status")
def get_data_status() -> dict:
    settings = get_settings()
    status = data_status(Path(settings.data_root))
    lean = LeanQuantEngine(
        lean_image=settings.lean_image,
        data_root=Path(settings.data_root),
        jobs_root=Path(settings.jobs_root),
    ).health_check()
    status["lean_engine"] = lean
    return status


@router.post("/ingest/spy")
def ingest_spy_endpoint(payload: IngestRequest, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    try:
        result = ingest_spy(
            data_root=Path(settings.data_root),
            start=payload.start,
            end=payload.end,
            provider=payload.provider,
            convert_lean=payload.convert_lean,
        )
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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    snapshot = snapshot_service.upsert_snapshot_from_ingest(db, result)
    db.commit()
    parquet = result.get("parquet")
    return {
        "ok": True,
        "parquet": str(parquet) if parquet is not None else None,
        "snapshot_key": result.get("snapshot_key"),
        "data_snapshot_id": str(snapshot.id),
        "quality_report": result.get("quality_report"),
        "status": data_status(Path(settings.data_root)),
    }
