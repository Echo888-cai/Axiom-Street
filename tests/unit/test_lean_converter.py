from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from quant.data.duckdb_query import connect_market
from quant.data.ingest_spy import data_status, latest_snapshot_dir, load_spy_parquet
from quant.data.lean_converter import (
    bars_to_lean_daily_csv,
    build_factor_file,
    convert_spy_to_lean,
    convert_to_lean,
    ensure_lean_spy_data,
)
from quant.data.manifest import save_manifest
from quant.data.providers import fetch_stooq
from quant.data.types import ProviderCapabilityError


def test_bars_to_lean_daily_csv_deci_cents():
    df = pd.DataFrame(
        [
            {
                "timestamp": datetime(2020, 1, 2, tzinfo=timezone.utc),
                "open": 100.0,
                "high": 101.0,
                "low": 99.5,
                "close": 100.5,
                "volume": 1_000_000,
            }
        ]
    )
    csv = bars_to_lean_daily_csv(df)
    assert "20200101" in csv or "20200102" in csv
    assert "1005000" in csv  # 100.5 * 10000
    assert "1000000" in csv


def test_factor_file_includes_dividend_event():
    df = pd.DataFrame(
        [
            {
                "timestamp": datetime(2020, 1, 2, tzinfo=timezone.utc),
                "open": 100,
                "high": 100,
                "low": 100,
                "close": 100,
                "volume": 1,
                "dividends": 1.0,
                "stock_splits": 0.0,
            },
            {
                "timestamp": datetime(2020, 2, 3, tzinfo=timezone.utc),
                "open": 100,
                "high": 100,
                "low": 100,
                "close": 100,
                "volume": 1,
                "dividends": 0.0,
                "stock_splits": 2.0,
            },
        ]
    )
    text = build_factor_file(df)
    assert "20501231,1,1,0" in text
    assert "20200101" in text or "20200102" in text
    assert "20200202" in text or "20200203" in text


def _spy_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": datetime(2020, 1, 2, tzinfo=timezone.utc),
                "open": 100.0,
                "high": 101.0,
                "low": 99.5,
                "close": 100.5,
                "volume": 1_000_000,
                "dividends": 0.5,
                "stock_splits": 0.0,
            }
        ]
    )


def test_convert_spy_to_lean_writes_zip(tmp_path: Path):
    parquet = tmp_path / "market" / "equities" / "US" / "daily" / "SPY.parquet"
    parquet.parent.mkdir(parents=True)
    _spy_df().to_parquet(parquet, index=False)
    save_manifest(tmp_path, {"corporate_actions_verified": True, "source": "yfinance"})
    lean = convert_spy_to_lean(tmp_path, require_corporate_actions=False)
    assert (lean / "equity" / "usa" / "daily" / "spy.zip").exists()
    assert (lean / "equity" / "usa" / "factor_files" / "spy.csv").exists()


def test_ensure_lean_spy_data_rejects_unverified_corporate_actions(tmp_path: Path):
    parquet = tmp_path / "market" / "equities" / "US" / "daily" / "SPY.parquet"
    parquet.parent.mkdir(parents=True)
    _spy_df().to_parquet(parquet, index=False)
    save_manifest(tmp_path, {"corporate_actions_verified": False, "source": "stooq"})
    with pytest.raises(ProviderCapabilityError, match="分红"):
        ensure_lean_spy_data(tmp_path)


def test_ensure_lean_spy_data_missing_parquet(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        ensure_lean_spy_data(tmp_path)


def test_load_spy_parquet_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_spy_parquet(tmp_path)


def test_data_status_not_ready(tmp_path: Path):
    status = data_status(tmp_path)
    assert status["ready"] is False
    assert status["lean_ready"] is False


def test_latest_snapshot_dir_empty(tmp_path: Path):
    assert latest_snapshot_dir(tmp_path) is None
    (tmp_path / "snapshots").mkdir()
    assert latest_snapshot_dir(tmp_path) is None


def test_connect_market_without_parquet(tmp_path: Path):
    con = connect_market(tmp_path)
    assert con is not None
    con.close()


def test_connect_market_with_parquet(tmp_path: Path):
    parquet = tmp_path / "market" / "equities" / "US" / "daily" / "SPY.parquet"
    parquet.parent.mkdir(parents=True)
    _spy_df().to_parquet(parquet, index=False)
    con = connect_market(tmp_path)
    n = con.execute("select count(*) from spy_daily").fetchone()[0]
    assert n == 1
    con.close()


def test_convert_to_lean_writes_qqq_zip(tmp_path: Path):
    qqq = _spy_df().copy()
    qqq["symbol"] = "QQQ"
    parquet = tmp_path / "market" / "equities" / "US" / "daily" / "QQQ.parquet"
    parquet.parent.mkdir(parents=True)
    qqq.to_parquet(parquet, index=False)
    save_manifest(tmp_path, {"corporate_actions_verified": True, "source": "yfinance"})
    lean = convert_to_lean(tmp_path, symbols=["QQQ"], require_corporate_actions=False)
    assert (lean / "equity" / "usa" / "daily" / "qqq.zip").exists()
    assert (lean / "equity" / "usa" / "factor_files" / "qqq.csv").exists()
    props = (lean / "symbol-properties" / "symbol-properties-database.csv").read_text()
    assert "QQQ," in props
    assert (lean / "equity" / "usa" / "map_files" / "qqq.csv").exists()


def test_fetch_stooq_parses_csv(monkeypatch):
    csv = pd.DataFrame(
        {
            "Date": ["2020-01-02", "2020-01-03"],
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [1000, 1100],
        }
    )
    monkeypatch.setattr("quant.data.providers.pd.read_csv", lambda *_a, **_k: csv)
    frame = fetch_stooq("SPY", start="2020-01-01", end="2020-01-03")
    assert len(frame) == 2
    assert list(frame["symbol"].unique()) == ["SPY"]
