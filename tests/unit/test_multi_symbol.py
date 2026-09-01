from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from quant.data.ingest_spy import ingest
from quant.data.providers import fetch_daily
from quant.data.symbols import as_symbol_list, normalize_symbols, snapshot_slug
from quant.data.types import YFINANCE_CAPABILITIES, FetchResult


def test_normalize_symbols_dedupes_and_uppercases():
    assert normalize_symbols(["spy", "SPY", " qqq "]) == ["SPY", "QQQ"]


def test_normalize_symbols_rejects_illegal():
    with pytest.raises(ValueError, match="非法"):
        normalize_symbols(["SPY", "not a ticker!!"])


def test_as_symbol_list_accepts_comma_string():
    assert as_symbol_list("SPY,QQQ") == ["SPY", "QQQ"]


def test_snapshot_slug_joins_then_hashes_long_lists():
    assert snapshot_slug(["SPY", "QQQ"]) == "spy-qqq"
    long = [f"S{i:02d}" for i in range(20)]
    slug = snapshot_slug(long)
    assert slug.startswith("eq20-")
    assert len(slug) < 20


def _frame(symbol: str) -> pd.DataFrame:
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
                "symbol": symbol,
            }
        )
    return pd.DataFrame(rows)


def test_ingest_two_symbols_writes_both_parquets(monkeypatch, tmp_path: Path):
    def fake_fetch(symbol: str, **_k):
        return FetchResult(_frame(symbol), "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest_spy.fetch_daily", fake_fetch)
    result = ingest(symbols=["SPY", "QQQ"], data_root=tmp_path, convert_lean=False)
    assert result["symbols"] == ["SPY", "QQQ"]
    snap = tmp_path / "snapshots" / result["snapshot_key"]
    assert (snap / "market" / "equities" / "US" / "daily" / "SPY.parquet").exists()
    assert (snap / "market" / "equities" / "US" / "daily" / "QQQ.parquet").exists()
    assert "spy-qqq-daily-" in result["snapshot_key"]


def test_fetch_daily_auto_uses_requested_symbol(monkeypatch):
    seen: list[str] = []

    def fake_yf(symbol: str, start: str = "2010-01-01", end=None):
        seen.append(symbol)
        return _frame(symbol)

    monkeypatch.setattr("quant.data.providers.fetch_yfinance", fake_yf)
    result = fetch_daily("QQQ", provider="yfinance")
    assert seen == ["QQQ"]
    assert result.source == "yfinance"
    assert list(result.frame["symbol"].unique()) == ["QQQ"]


def test_health_prefers_worker_heartbeat(client, monkeypatch):
    monkeypatch.setattr(
        "services.api.health.read_worker_health",
        lambda: {
            "docker_available": True,
            "image": "quantconnect/lean:16355",
            "reported_at": "2026-09-01T00:00:00+00:00",
        },
    )
    res = client.get("/health")
    assert res.status_code == 200
    docker = res.json()["checks"]["docker"]
    assert docker["ok"] is True
    assert docker["source"] == "worker"


def test_unknown_snapshot_id_returns_404(client, monkeypatch):
    monkeypatch.setattr(
        "services.api.services.backtests.data_status",
        lambda *_a, **_k: {
            "ready": True,
            "corporate_actions_verified": True,
            "manifest": {"sha256": "abc", "snapshot_key": "k", "source": "yfinance"},
            "symbols": ["SPY"],
        },
    )
    monkeypatch.setattr("services.api.services.backtests._quality_gate", lambda *_a, **_k: None)
    strategy = client.post("/api/v1/strategies", json={"name": "snap"}).json()
    res = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": strategy["latest_version"]["id"],
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
            "data_snapshot_id": str(uuid4()),
        },
    )
    assert res.status_code == 404


def test_missing_snapshot_dir_returns_409(client, monkeypatch):
    from types import SimpleNamespace

    sid = uuid4()
    monkeypatch.setattr(
        "services.api.services.backtests.snapshot_service.get_snapshot",
        lambda *_a, **_k: SimpleNamespace(
            id=sid, snapshot_key="missing-key", content_sha256="x", symbols=["SPY"]
        ),
    )
    strategy = client.post("/api/v1/strategies", json={"name": "snap2"}).json()
    res = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": strategy["latest_version"]["id"],
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
            "data_snapshot_id": str(sid),
        },
    )
    assert res.status_code == 409
    assert "快照文件" in res.json()["detail"]


def test_list_snapshots_empty(client):
    res = client.get("/api/v1/data/snapshots")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 0
    assert body["items"] == []
