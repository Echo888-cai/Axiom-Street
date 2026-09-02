"""Batch ingest throughput: rate limit, symbol cap, 500-name mocked snapshot."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from quant.data.ingest_spy import data_status, ingest
from quant.data.rate_limit import (
    TokenBucket,
    ensure_ingest_symbol_count,
    reset_ingest_limiter,
)
from quant.data.symbols import load_symbols_file, snapshot_slug
from quant.data.types import YFINANCE_CAPABILITIES, FetchResult


@pytest.fixture(autouse=True)
def _reset_limiter():
    reset_ingest_limiter()
    yield
    reset_ingest_limiter()


def _bars(symbol: str) -> pd.DataFrame:
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


def test_token_bucket_unlimited_is_noop():
    bucket = TokenBucket(rate=0)
    t0 = time.monotonic()
    for _ in range(20):
        bucket.acquire()
    assert time.monotonic() - t0 < 0.05


def test_token_bucket_enforces_rate():
    bucket = TokenBucket(rate=30.0, burst=1.0)
    t0 = time.monotonic()
    for _ in range(3):
        bucket.acquire()
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.05
    assert elapsed < 1.0


def test_unparseable_rps_fails_loud(monkeypatch):
    monkeypatch.setenv("STREET_INGEST_RPS", "fast")
    reset_ingest_limiter()
    from quant.data.rate_limit import ingest_rps

    with pytest.raises(ValueError, match="STREET_INGEST_RPS"):
        ingest_rps()


def test_symbol_cap_fails_loud(monkeypatch):
    monkeypatch.setenv("STREET_INGEST_MAX_SYMBOLS", "2")
    with pytest.raises(ValueError, match="at most 2 symbols"):
        ensure_ingest_symbol_count(3)


def test_load_symbols_file_strips_comments(tmp_path: Path):
    path = tmp_path / "tickers.txt"
    path.write_text("# universe\nSPY\n\nQQQ  # nasdaq\nIWM\n", encoding="utf-8")
    assert load_symbols_file(path) == ["SPY", "QQQ", "IWM"]


def test_load_symbols_file_empty_fails(tmp_path: Path):
    path = tmp_path / "empty.txt"
    path.write_text("# none\n\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no tickers"):
        load_symbols_file(path)


def test_ingest_rejects_over_max_symbols(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STREET_INGEST_MAX_SYMBOLS", "2")
    monkeypatch.setattr(
        "quant.data.ingest_spy.fetch_daily",
        lambda symbol, **_k: FetchResult(_bars(symbol), "yfinance", YFINANCE_CAPABILITIES),
    )
    with pytest.raises(ValueError, match="at most 2 symbols"):
        ingest(symbols=["SPY", "QQQ", "IWM"], data_root=tmp_path, convert_lean=False)


def test_concurrent_ingest_writes_every_symbol(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STREET_INGEST_CONCURRENCY", "4")
    monkeypatch.setenv("STREET_INGEST_RPS", "0")
    tickers = [f"A{i:03d}" for i in range(12)]
    monkeypatch.setattr(
        "quant.data.ingest_spy.fetch_daily",
        lambda symbol, **_k: FetchResult(_bars(symbol), "yfinance", YFINANCE_CAPABILITIES),
    )
    result = ingest(symbols=tickers, data_root=tmp_path, convert_lean=False)
    assert result["symbols"] == tickers
    daily = tmp_path / "market" / "equities" / "US" / "daily"
    assert all((daily / f"{s}.parquet").exists() for s in tickers)


def test_ingest_500_symbols_writes_lean(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STREET_INGEST_CONCURRENCY", "8")
    monkeypatch.setenv("STREET_INGEST_RPS", "0")
    monkeypatch.setenv("STREET_INGEST_MAX_SYMBOLS", "500")
    tickers = [f"A{i:03d}" for i in range(500)]
    monkeypatch.setattr(
        "quant.data.ingest_spy.fetch_daily",
        lambda symbol, **_k: FetchResult(_bars(symbol), "yfinance", YFINANCE_CAPABILITIES),
    )
    result = ingest(symbols=tickers, data_root=tmp_path, convert_lean=True)
    assert len(result["symbols"]) == 500
    assert result["snapshot_key"].startswith("eq500-")
    assert snapshot_slug(tickers).startswith("eq500-")
    daily = tmp_path / "market" / "equities" / "US" / "daily"
    lean = tmp_path / "lean" / "equity" / "usa" / "daily"
    assert (daily / "A000.parquet").exists()
    assert (daily / "A499.parquet").exists()
    assert (lean / "a000.zip").exists()
    assert (lean / "a499.zip").exists()
    status = data_status(tmp_path)
    assert status["lean_ready"] is True
    assert status["ingest_limits"]["max_symbols"] == 500


def test_api_rejects_over_max_symbols(client, monkeypatch):
    monkeypatch.setenv("STREET_INGEST_MAX_SYMBOLS", "1")
    res = client.post(
        "/api/v1/data/ingest",
        json={"symbols": ["SPY", "QQQ"], "provider": "yfinance", "convert_lean": False},
    )
    assert res.status_code == 400
    assert "at most 1 symbols" in res.json()["detail"]
