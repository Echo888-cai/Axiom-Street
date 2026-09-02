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
