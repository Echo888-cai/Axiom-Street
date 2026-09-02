"""Async ingest jobs: progress callback, Celery-sync path, API enqueue."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from quant.data.ingest_spy import ingest
from quant.data.types import YFINANCE_CAPABILITIES, FetchResult


def _frame(symbol: str) -> pd.DataFrame:
    rows = []
    for day in (2, 3, 6, 7):
        rows.append(
            {
                "timestamp": datetime(2020, 1, day, tzinfo=timezone.utc),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0 + day * 0.1,
                "volume": 1000,
                "dividends": 0.0,
                "stock_splits": 0.0,
                "exchange_timezone": "America/New_York",
                "symbol": symbol,
            }
        )
    return pd.DataFrame(rows)


def test_ingest_on_progress_reports_each_symbol(monkeypatch, tmp_path: Path):
    seen: list[tuple[str, int, int]] = []

    def fake_fetch(symbol: str, **_k):
        return FetchResult(_frame(symbol), "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest_spy.fetch_daily", fake_fetch)
    ingest(
        symbols=["SPY", "QQQ"],
        data_root=tmp_path,
        convert_lean=False,
        on_progress=lambda symbol, index, total: seen.append((symbol, index, total)),
    )
    assert seen == [("SPY", 1, 2), ("QQQ", 2, 2)]


def test_create_ingest_job_sync_completes(client, monkeypatch, tmp_path: Path):
    from services.api.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("STREET_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()

    def fake_fetch(symbol: str, **_k):
        return FetchResult(_frame(symbol), "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest_spy.fetch_daily", fake_fetch)

    res = client.post(
        "/api/v1/data/ingest",
        json={"symbols": ["SPY", "QQQ"], "provider": "yfinance", "convert_lean": False},
    )
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "COMPLETED"
    assert body["total_symbols"] == 2
    assert body["completed_symbols"] == 2
    assert body["result"]["ok"] is True
    assert body["data_snapshot_id"]

    detail = client.get(f"/api/v1/data/ingest/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "COMPLETED"
