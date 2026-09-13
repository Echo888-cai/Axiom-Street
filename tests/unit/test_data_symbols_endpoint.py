"""GET /api/v1/data/symbols: catalog for symbol pickers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

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


def test_list_symbols_empty_when_no_data(client, monkeypatch, tmp_path: Path):
    from services.api.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("STREET_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()

    res = client.get("/api/v1/data/symbols")
    assert res.status_code == 200
    assert res.json() == {"total": 0, "items": []}
    get_settings.cache_clear()


def test_list_symbols_reports_real_per_symbol_coverage(client, monkeypatch, tmp_path: Path):
    from services.api.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("STREET_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()

    def fake_fetch(symbol: str, **_k):
        return FetchResult(_frame(symbol), "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest.fetch_daily", fake_fetch)

    ingest = client.post(
        "/api/v1/data/ingest",
        json={"symbols": ["SPY", "QQQ"], "provider": "yfinance", "convert_lean": False},
    )
    assert ingest.status_code == 202, ingest.text
    assert ingest.json()["status"] == "COMPLETED"

    res = client.get("/api/v1/data/symbols")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    by_symbol = {row["symbol"]: row for row in body["items"]}
    assert set(by_symbol) == {"SPY", "QQQ"}
    for row in by_symbol.values():
        assert row["row_count"] == 4
        assert row["date_range_start"].startswith("2020-01-02")
        assert row["date_range_end"].startswith("2020-01-07")
        assert row["provider"] == "yfinance"
    get_settings.cache_clear()


def test_list_symbols_reflects_per_symbol_row_counts_not_aggregate(
    client, monkeypatch, tmp_path: Path
):
    """SPY and QQQ ingested together but with different real coverage.

    Guards against regressing to DataSnapshot.row_count / manifest "rows",
    which are aggregates across every symbol in one ingest call.
    """
    from services.api.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("STREET_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()

    def fake_fetch(symbol: str, **_k):
        frame = _frame(symbol)
        if symbol == "QQQ":
            frame = frame.iloc[:2]
        return FetchResult(frame, "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest.fetch_daily", fake_fetch)

    ingest = client.post(
        "/api/v1/data/ingest",
        json={"symbols": ["SPY", "QQQ"], "provider": "yfinance", "convert_lean": False},
    )
    assert ingest.status_code == 202, ingest.text

    res = client.get("/api/v1/data/symbols")
    by_symbol = {row["symbol"]: row for row in res.json()["items"]}
    assert by_symbol["SPY"]["row_count"] == 4
    assert by_symbol["QQQ"]["row_count"] == 2
    get_settings.cache_clear()
