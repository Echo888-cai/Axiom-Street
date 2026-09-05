"""Scheduled full market reconcile: restatement detection + Beat entrypoint."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from quant.data.ingest import ingest
from quant.data.types import YFINANCE_CAPABILITIES, FetchResult
from services.api.settings import get_settings
from services.worker.celery_app import celery_app


def _bars(symbol: str, days: list[int], *, close_base: float = 100.0) -> pd.DataFrame:
    rows = []
    for day in days:
        rows.append(
            {
                "timestamp": datetime(2020, 1, day, tzinfo=timezone.utc),
                "open": close_base,
                "high": close_base + 1,
                "low": close_base - 1,
                "close": close_base + day * 0.1,
                "volume": 1000,
                "dividends": 0.0,
                "stock_splits": 0.0,
                "exchange_timezone": "America/New_York",
                "symbol": symbol,
            }
        )
    return pd.DataFrame(rows)


def test_full_ingest_flags_vendor_restatement_against_prior(monkeypatch, tmp_path: Path):
    def first_fetch(symbol: str, **_k):
        return FetchResult(_bars(symbol, [2, 3, 6, 7]), "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest.fetch_daily", first_fetch)
    first = ingest(symbols=["SPY"], data_root=tmp_path, convert_lean=False, mode="full")
    prior_key = first["snapshot_key"]

    def revised_fetch(symbol: str, **_k):
        frame = _bars(symbol, [2, 3, 6, 7, 8])
        mask = frame["timestamp"] == datetime(2020, 1, 7, tzinfo=timezone.utc)
        frame.loc[mask, "close"] = 101.2
        frame.loc[mask, "high"] = 102.0
        return FetchResult(frame, "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest.fetch_daily", revised_fetch)
    second = ingest(symbols=["SPY"], data_root=tmp_path, convert_lean=False, mode="full")
    assert second["snapshot_key"] != prior_key
    assert any(i["rule"] == "vendor_restatement" for i in second["quality_report"]["issues"])


def test_beat_schedule_includes_market_reconcile_when_enabled():
    assert "reconcile-market-data" in celery_app.conf.beat_schedule
    entry = celery_app.conf.beat_schedule["reconcile-market-data"]
    assert entry["task"] == "data.reconcile_market"
    assert float(entry["schedule"]) >= 60.0


def test_schedule_market_reconcile_skips_without_symbols(tmp_path: Path, monkeypatch):
    from services.api.services import ingest_jobs as jobs

    monkeypatch.setenv("STREET_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    result = jobs.schedule_market_reconcile(force=True)
    assert result["skipped"] is True
    assert result["reason"] == "no_symbols"
    get_settings.cache_clear()


def test_schedule_skips_when_disabled_for_beat(monkeypatch, tmp_path: Path):
    from services.api.services import ingest_jobs as jobs

    monkeypatch.setenv("STREET_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("STREET_MARKET_RECONCILE_ENABLED", "false")
    get_settings.cache_clear()
    result = jobs.schedule_market_reconcile(force=False, scheduled=True)
    assert result["skipped"] is True
    assert result["reason"] == "disabled"
    get_settings.cache_clear()


def test_schedule_market_reconcile_enqueues_full_job(client, monkeypatch, tmp_path: Path):
    get_settings.cache_clear()
    monkeypatch.setenv("STREET_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()

    def fake_fetch(symbol: str, **_k):
        return FetchResult(_bars(symbol, [2, 3, 6, 7]), "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest.fetch_daily", fake_fetch)

    seed = client.post(
        "/api/v1/data/ingest",
        json={"symbols": ["SPY", "QQQ"], "provider": "yfinance", "convert_lean": False},
    )
    assert seed.status_code == 202
    assert seed.json()["status"] == "COMPLETED"

    res = client.post("/api/v1/data/reconcile")
    assert res.status_code == 202
    body = res.json()
    assert body["ok"] is True
    assert body["job"]["mode"] == "full"
    assert set(body["symbols"]) == {"SPY", "QQQ"}
    assert body["job"]["status"] == "COMPLETED"

    status = client.get("/api/v1/data/status").json()
    assert status["market_reconcile"]["enabled"] is True
    assert status["latest_ingest_job"]["id"] == body["job"]["id"]


def test_schedule_skips_when_ingest_running(client, monkeypatch, tmp_path: Path):
    from services.api import db as db_module
    from services.api.models import IngestJob, IngestJobStatus

    get_settings.cache_clear()
    monkeypatch.setenv("STREET_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()

    def fake_fetch(symbol: str, **_k):
        return FetchResult(_bars(symbol, [2, 3, 6, 7]), "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest.fetch_daily", fake_fetch)

    seed = client.post(
        "/api/v1/data/ingest",
        json={"symbols": ["SPY"], "provider": "yfinance", "convert_lean": False},
    )
    assert seed.status_code == 202

    db = db_module.SessionLocal()
    try:
        db.add(
            IngestJob(
                status=IngestJobStatus.RUNNING,
                symbols=["SPY"],
                total_symbols=1,
                progress_step="Fetching SPY (1/1)",
            )
        )
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/data/reconcile")
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["reason"] == "ingest_in_progress"
    assert "active_job_id" in detail


def test_manual_reconcile_still_runs_when_beat_disabled(client, monkeypatch, tmp_path: Path):
    get_settings.cache_clear()
    monkeypatch.setenv("STREET_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("STREET_MARKET_RECONCILE_ENABLED", "false")
    get_settings.cache_clear()

    def fake_fetch(symbol: str, **_k):
        return FetchResult(_bars(symbol, [2, 3, 6, 7]), "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest.fetch_daily", fake_fetch)

    seed = client.post(
        "/api/v1/data/ingest",
        json={"symbols": ["SPY"], "provider": "yfinance", "convert_lean": False},
    )
    assert seed.status_code == 202

    res = client.post("/api/v1/data/reconcile")
    assert res.status_code == 202
    assert res.json()["ok"] is True
    get_settings.cache_clear()
