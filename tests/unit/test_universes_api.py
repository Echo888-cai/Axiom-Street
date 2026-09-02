from __future__ import annotations

import pandas as pd


def _ready(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.api.services.backtests.data_status",
        lambda *_a, **_k: {
            "ready": True,
            "corporate_actions_verified": True,
            "manifest": {
                "sha256": "abc123",
                "snapshot_key": "spy-daily-test-abc123",
                "source": "yfinance",
            },
            "symbols": ["SPY"],
        },
    )
    monkeypatch.setattr("services.api.services.backtests._quality_gate", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "services.api.services.snapshots.ensure_snapshot_row", lambda *_a, **_k: None
    )


def test_universe_crud_and_preview(client):
    created = client.post(
        "/api/v1/universes",
        json={
            "name": "美股核心",
            "description": "含退市成分",
            "members": [
                {"symbol": "SPY", "effective_from": "2010-01-04"},
                {"symbol": "BBBY", "effective_from": "2010-01-04", "effective_to": "2018-03-23"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["kind"] == "STATIC"
    assert body["member_count"] == 2
    symbols = {row["symbol"] for row in body["members"]}
    assert symbols == {"SPY", "BBBY"}

    listed = client.get("/api/v1/universes")
    assert listed.status_code == 200
    page = listed.json()
    assert page["total"] == 1
    assert page["items"][0]["member_count"] == 2
    assert page["items"][0]["members"] == []

    as_of = client.get(
        f"/api/v1/universes/{body['id']}/constituents", params={"as_of": "2018-03-24"}
    )
    assert as_of.status_code == 200
    assert as_of.json()["symbols"] == ["SPY"]

    window = client.get(
        f"/api/v1/universes/{body['id']}/constituents",
        params={"start": "2018-01-01", "end": "2020-12-31"},
    )
    assert window.status_code == 200
    assert window.json()["symbols"] == ["SPY", "BBBY"]


def test_overlapping_membership_is_rejected(client):
    created = client.post("/api/v1/universes", json={"name": "overlap"}).json()
    first = client.post(
        f"/api/v1/universes/{created['id']}/members",
        json={"symbol": "X", "effective_from": "2010-01-01", "effective_to": "2015-12-31"},
    )
    assert first.status_code == 201, first.text
    clash = client.post(
        f"/api/v1/universes/{created['id']}/members",
        json={"symbol": "X", "effective_from": "2015-06-01", "effective_to": "2020-01-01"},
    )
    assert clash.status_code == 400
    assert "重叠" in clash.json()["detail"]


def test_infer_effective_to_without_parquet_is_409(client, monkeypatch):
    def missing(_root, symbol):
        raise FileNotFoundError(symbol)

    monkeypatch.setattr("services.api.services.universes.load_symbol_parquet", missing)
    created = client.post("/api/v1/universes", json={"name": "infer"}).json()
    res = client.post(
        f"/api/v1/universes/{created['id']}/members",
        json={
            "symbol": "BBBY",
            "effective_from": "2010-01-04",
            "infer_effective_to_from_data": True,
        },
    )
    assert res.status_code == 409
    assert "BBBY" in res.json()["detail"]


def test_infer_effective_to_from_stale_bars(client, monkeypatch):
    frame = pd.DataFrame({"timestamp": [pd.Timestamp("2018-03-23")]})
    monkeypatch.setattr(
        "services.api.services.universes.load_symbol_parquet",
        lambda *_a, **_k: frame,
    )
    monkeypatch.setattr(
        "services.api.services.universes.infer_effective_to_from_bars",
        lambda last_bar, **_k: last_bar,
    )
    created = client.post("/api/v1/universes", json={"name": "stale"}).json()
    res = client.post(
        f"/api/v1/universes/{created['id']}/members",
        json={
            "symbol": "BBBY",
            "effective_from": "2010-01-04",
            "infer_effective_to_from_data": True,
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["effective_to"] == "2018-03-23"


def test_create_backtest_with_universe_id_snapshots_memberships(client, monkeypatch):
    _ready(monkeypatch)
    universe = client.post(
        "/api/v1/universes",
        json={
            "name": "回测池",
            "members": [
                {"symbol": "SPY", "effective_from": "2010-01-04"},
                {"symbol": "BBBY", "effective_from": "2010-01-04", "effective_to": "2018-03-23"},
            ],
        },
    ).json()
    strategy = client.post("/api/v1/strategies", json={"name": "u"}).json()
    created = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": strategy["latest_version"]["id"],
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
            "universe_id": universe["id"],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["universe_id"] == universe["id"]
    snapshot = body["universe_snapshot"]
    assert snapshot is not None
    symbols = {row["symbol"] for row in snapshot}
    assert symbols == {"SPY", "BBBY"}


def test_create_backtest_empty_universe_window_is_422(client, monkeypatch):
    _ready(monkeypatch)
    universe = client.post(
        "/api/v1/universes",
        json={
            "name": "未来池",
            "members": [{"symbol": "SPY", "effective_from": "2020-01-01"}],
        },
    ).json()
    strategy = client.post("/api/v1/strategies", json={"name": "empty-u"}).json()
    res = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": strategy["latest_version"]["id"],
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
            "universe_id": universe["id"],
        },
    )
    assert res.status_code == 422
    assert "没有成分" in res.json()["detail"]


def test_create_backtest_with_ten_symbols_snapshots_memberships(client, monkeypatch):
    from quant.strategy_sdk.equal_weight import DEFAULT_EQUAL_WEIGHT_UNIVERSE

    _ready(monkeypatch)
    strategy = client.post("/api/v1/strategies", json={"name": "ten"}).json()
    created = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": strategy["latest_version"]["id"],
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
            "universe": list(DEFAULT_EQUAL_WEIGHT_UNIVERSE),
        },
    )
    assert created.status_code == 201, created.text
    snapshot = created.json()["universe_snapshot"]
    assert snapshot is not None
    assert [row["symbol"] for row in snapshot] == list(DEFAULT_EQUAL_WEIGHT_UNIVERSE)


def test_universe_id_and_symbols_cannot_both_be_set(client, monkeypatch):
    _ready(monkeypatch)
    universe = client.post("/api/v1/universes", json={"name": "both"}).json()
    strategy = client.post("/api/v1/strategies", json={"name": "both"}).json()
    res = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": strategy["latest_version"]["id"],
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
            "universe_id": universe["id"],
            "universe": ["SPY"],
        },
    )
    assert res.status_code == 400


def test_unknown_universe_is_404(client):
    res = client.get("/api/v1/universes/00000000-0000-0000-0000-000000000001")
    assert res.status_code == 404


def test_sync_delistings_closes_stale_open_members(client, monkeypatch):
    frame = pd.DataFrame({"timestamp": [pd.Timestamp("2018-03-23")]})
    monkeypatch.setattr(
        "services.api.services.universes.load_symbol_parquet",
        lambda *_a, **_k: frame,
    )
    created = client.post(
        "/api/v1/universes",
        json={
            "name": "sync-delist",
            "members": [{"symbol": "BBBY", "effective_from": "2010-01-04"}],
        },
    ).json()
    res = client.post("/api/v1/universes/sync-delistings")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["applied"][0]["symbol"] == "BBBY"
    assert body["applied"][0]["effective_to"] == "2018-03-23"
    got = client.get(f"/api/v1/universes/{created['id']}").json()
    assert got["members"][0]["effective_to"] == "2018-03-23"


def test_ingest_delisted_symbol_records_effective_to(client, monkeypatch, tmp_path):
    from datetime import datetime, timezone

    from quant.data.types import YFINANCE_CAPABILITIES, FetchResult
    from services.api.settings import get_settings

    monkeypatch.setenv("STREET_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()

    def fake_fetch(symbol: str, **_k):
        rows = []
        for day in (19, 20, 21, 22, 23):
            rows.append(
                {
                    "timestamp": datetime(2018, 3, day, tzinfo=timezone.utc),
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.0,
                    "close": 10.0,
                    "volume": 1000,
                    "dividends": 0.0,
                    "stock_splits": 0.0,
                    "exchange_timezone": "America/New_York",
                    "symbol": symbol,
                }
            )
        return FetchResult(pd.DataFrame(rows), "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest_spy.fetch_daily", fake_fetch)
    universe = client.post(
        "/api/v1/universes",
        json={
            "name": "含退市",
            "members": [
                {"symbol": "BBBY", "effective_from": "2010-01-04"},
                {"symbol": "SPY", "effective_from": "2010-01-04", "effective_to": "2017-01-01"},
            ],
        },
    ).json()
    ingest = client.post(
        "/api/v1/data/ingest",
        json={"symbols": ["BBBY"], "provider": "yfinance", "convert_lean": False},
    )
    assert ingest.status_code == 202, ingest.text
    job = ingest.json()
    assert job["status"] == "COMPLETED"
    applied = (job.get("result") or {}).get("universe_delistings", {}).get("applied") or []
    assert any(row["symbol"] == "BBBY" and row["effective_to"] == "2018-03-23" for row in applied)
    got = client.get(f"/api/v1/universes/{universe['id']}").json()
    by_symbol = {row["symbol"]: row["effective_to"] for row in got["members"]}
    assert by_symbol["BBBY"] == "2018-03-23"
    assert by_symbol["SPY"] == "2017-01-01"
    get_settings.cache_clear()


def test_rule_universe_rejects_manual_members(client):
    res = client.post(
        "/api/v1/universes",
        json={
            "name": "rule-manual",
            "kind": "RULE",
            "rules": {"min_price": 5},
            "members": [{"symbol": "SPY", "effective_from": "2010-01-04"}],
        },
    )
    assert res.status_code == 400


def test_rule_universe_builds_from_snapshot(client, monkeypatch, tmp_path):
    from datetime import datetime, timezone

    from quant.data.types import YFINANCE_CAPABILITIES, FetchResult
    from services.api.settings import get_settings

    monkeypatch.setenv("STREET_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()

    def fake_fetch(symbol: str, **_k):
        close = 100.0 if symbol == "SPY" else 8.0
        rows = []
        for day in (2, 3, 6, 7):
            rows.append(
                {
                    "timestamp": datetime(2020, 1, day, tzinfo=timezone.utc),
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1000,
                    "dividends": 0.0,
                    "stock_splits": 0.0,
                    "exchange_timezone": "America/New_York",
                    "symbol": symbol,
                }
            )
        return FetchResult(pd.DataFrame(rows), "yfinance", YFINANCE_CAPABILITIES)

    monkeypatch.setattr("quant.data.ingest_spy.fetch_daily", fake_fetch)
    ingest = client.post(
        "/api/v1/data/ingest",
        json={"symbols": ["SPY", "QQQ"], "provider": "yfinance", "convert_lean": False},
    )
    assert ingest.status_code == 202, ingest.text
    created = client.post(
        "/api/v1/universes",
        json={
            "name": "流动池",
            "kind": "RULE",
            "rules": {"min_price": 10, "lookback_days": 1},
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["kind"] == "RULE"
    assert {row["symbol"] for row in body["members"]} == {"SPY"}
    assert body["members"][0]["effective_to"] is None
    blocked = client.post(
        f"/api/v1/universes/{body['id']}/members",
        json={"symbol": "QQQ", "effective_from": "2020-01-02"},
    )
    assert blocked.status_code == 400
    get_settings.cache_clear()
