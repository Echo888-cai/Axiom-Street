from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from quant.data.ingest_spy import data_status, ingest_spy
from quant.engine.lean import LeanQuantEngine
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
def ingest_spy_endpoint(payload: IngestRequest) -> dict:
    settings = get_settings()
    try:
        path = ingest_spy(
            data_root=Path(settings.data_root),
            start=payload.start,
            end=payload.end,
            provider=payload.provider,
            convert_lean=payload.convert_lean,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "ok": True,
        "parquet": str(path),
        "status": data_status(Path(settings.data_root)),
    }
