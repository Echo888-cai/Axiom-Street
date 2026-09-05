"""Incremental ingest: append-only fetch windows, immutable snapshots, restatement warnings."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from quant.data.ingest import ingest
from quant.data.types import YFINANCE_CAPABILITIES, FetchResult


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


def test_incremental_requires_prior_snapshot(tmp_path: Path):
    with pytest.raises(ValueError, match="requires prior bars"):
        ingest(symbols=["SPY"], data_root=tmp_path, convert_lean=False, mode="incremental")


def test_incremental_fetches_only_after_last_bar(monkeypatch, tmp_path: Path):
    calls: list[tuple[str, str]] = []

    def fake_fetch(symbol: str, *, start: str = "2010-01-01", end=None, **_k):
        calls.append((symbol, start))
        if start <= "2020-01-01":
            return FetchResult(_bars(symbol, [2, 3, 6, 7]), "yfinance", YFINANCE_CAPABILITIES)
        return FetchResult(_bars(symbol, [8, 9, 10]), "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest.fetch_daily", fake_fetch)

    first = ingest(symbols=["SPY"], data_root=tmp_path, convert_lean=False, mode="full")
    prior_key = first["snapshot_key"]
    prior_dir = tmp_path / "snapshots" / prior_key
    assert prior_dir.exists()

    second = ingest(symbols=["SPY"], data_root=tmp_path, convert_lean=False, mode="incremental")
    assert second["ingest_mode"] == "incremental"
    assert second["prior_snapshot_key"] == prior_key
    assert second["snapshot_key"] != prior_key
    assert second["fetch_windows"]["SPY"]["start"] == "2020-01-08"
    # Prior snapshot directory must remain untouched.
    assert prior_dir.exists()
    prior_rows = len(pd.read_parquet(prior_dir / "market/equities/US/daily/SPY.parquet"))
    assert prior_rows == 4

    merged = pd.read_parquet(
        tmp_path / "snapshots" / second["snapshot_key"] / "market/equities/US/daily/SPY.parquet"
    )
    assert len(merged) == 7
    # Only the incremental call should have used the day-after-last start.
    assert ("SPY", "2020-01-08") in calls


def test_incremental_restatement_warns_and_writes_new_snapshot(monkeypatch, tmp_path: Path):
    def full_fetch(symbol: str, *, start: str = "2010-01-01", end=None, **_k):
        return FetchResult(
            _bars(symbol, [2, 3, 6, 7], close_base=100.0), "yfinance", YFINANCE_CAPABILITIES
        )

    monkeypatch.setattr("quant.data.ingest.fetch_daily", full_fetch)
    first = ingest(symbols=["SPY"], data_root=tmp_path, convert_lean=False, mode="full")
    prior_path = (
        tmp_path / "snapshots" / first["snapshot_key"] / "market/equities/US/daily/SPY.parquet"
    )
    prior_bytes = prior_path.read_bytes()

    def revised_fetch(symbol: str, *, start: str = "2010-01-01", end=None, **_k):
        # Overlap day 7 with a modest restated close (>1bp), plus one new day.
        frame = _bars(symbol, [7, 8], close_base=100.0)
        mask = frame["timestamp"] == datetime(2020, 1, 7, tzinfo=timezone.utc)
        # Original day-7 close was 100.7; restate ~50 bps and keep OHLC consistent.
        frame.loc[mask, "close"] = 101.2
        frame.loc[mask, "high"] = 102.0
        frame.loc[mask, "open"] = 100.0
        frame.loc[mask, "low"] = 99.0
        return FetchResult(frame, "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest.fetch_daily", revised_fetch)
    second = ingest(symbols=["SPY"], data_root=tmp_path, convert_lean=False, mode="incremental")

    assert second["snapshot_key"] != first["snapshot_key"]
    assert prior_path.read_bytes() == prior_bytes  # never mutated in place
    issues = second["quality_report"]["issues"]
    assert any(i["rule"] == "vendor_restatement" for i in issues)
    assert any(i["severity"] == "warning" for i in issues if i["rule"] == "vendor_restatement")


def test_unknown_mode_fails_loud(tmp_path: Path):
    with pytest.raises(ValueError, match="unsupported ingest mode"):
        ingest(symbols=["SPY"], data_root=tmp_path, convert_lean=False, mode="append")
