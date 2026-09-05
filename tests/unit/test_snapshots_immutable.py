from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from quant.data.ingest import ingest_spy
from quant.data.types import YFINANCE_CAPABILITIES, FetchResult


def _spy_frame() -> pd.DataFrame:
    rows = []
    for day in (2, 3, 6, 7, 8, 9, 10):
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
                "symbol": "SPY",
            }
        )
    return pd.DataFrame(rows)


def test_ingest_is_immutable_and_content_addressed(monkeypatch, tmp_path: Path):
    frame = _spy_frame()
    monkeypatch.setattr(
        "quant.data.ingest.fetch_daily",
        lambda *_a, **_k: FetchResult(frame.copy(), "yfinance", YFINANCE_CAPABILITIES),
    )
    first = ingest_spy(data_root=tmp_path, convert_lean=False)
    second = ingest_spy(data_root=tmp_path, convert_lean=False)
    assert first["snapshot_key"] == second["snapshot_key"]
    assert second["deduplicated"] is True
    snap_dirs = list((tmp_path / "snapshots").iterdir())
    assert len(snap_dirs) == 1
    assert (snap_dirs[0] / "market" / "equities" / "US" / "daily" / "SPY.parquet").exists()


def test_second_ingest_keeps_prior_snapshot(monkeypatch, tmp_path: Path):
    frame = _spy_frame()

    def fetch(*_a, **_k):
        out = frame.copy()
        new_close = float(out.loc[out.index[-1], "close"]) + 1.0
        out.loc[out.index[-1], "close"] = new_close
        out.loc[out.index[-1], "high"] = max(float(out.loc[out.index[-1], "high"]), new_close)
        frame.loc[frame.index[-1], "close"] = new_close
        frame.loc[frame.index[-1], "high"] = max(
            float(frame.loc[frame.index[-1], "high"]), new_close
        )
        return FetchResult(out, "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest.fetch_daily", fetch)
    a = ingest_spy(data_root=tmp_path, convert_lean=False)
    b = ingest_spy(data_root=tmp_path, convert_lean=False)
    assert a["snapshot_key"] != b["snapshot_key"]
    keys = {p.name for p in (tmp_path / "snapshots").iterdir() if p.is_dir()}
    assert a["snapshot_key"] in keys
    assert b["snapshot_key"] in keys
    first_parquet = (
        tmp_path
        / "snapshots"
        / a["snapshot_key"]
        / "market"
        / "equities"
        / "US"
        / "daily"
        / "SPY.parquet"
    )
    assert first_parquet.exists()
