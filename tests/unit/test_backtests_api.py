from __future__ import annotations


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


def _strategy(client):
    res = client.post("/api/v1/strategies", json={"name": "bt"})
    assert res.status_code == 201, res.text
    return res.json()


def test_list_backtests_is_paginated(client, monkeypatch):
    _ready(monkeypatch)
    listed = client.get("/api/v1/backtests")
    assert listed.status_code == 200
    body = listed.json()
    assert "items" in body and "total" in body
    assert body["total"] == 0


def test_create_backtest_writes_trial(client, monkeypatch):
    _ready(monkeypatch)
    strategy = _strategy(client)
    version_id = strategy["latest_version"]["id"]
    created = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": version_id,
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
        },
    )
    assert created.status_code == 201, created.text
    stats = client.get(f"/api/v1/strategies/{strategy['id']}/trial-stats")
    assert stats.status_code == 200
    payload = stats.json()
    assert payload["total_trials"] == 1
    listed = client.get("/api/v1/backtests")
    assert listed.json()["total"] == 1


def test_cancel_backtest(client, monkeypatch):
    _ready(monkeypatch)
    strategy = _strategy(client)
    created = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": strategy["latest_version"]["id"],
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
        },
    ).json()
    cancelled = client.post(f"/api/v1/backtests/{created['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"


def test_inflight_limit_returns_429(client, monkeypatch):
    _ready(monkeypatch)
    from services.api.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AXIOM_MAX_INFLIGHT_BACKTESTS", "1")
    get_settings.cache_clear()
    strategy = _strategy(client)
    body = {
        "strategy_version_id": strategy["latest_version"]["id"],
        "start_date": "2018-01-01",
        "end_date": "2018-06-01",
    }
    first = client.post("/api/v1/backtests", json=body)
    assert first.status_code == 201, first.text
    second = client.post("/api/v1/backtests", json={**body, "end_date": "2018-07-01"})
    assert second.status_code == 429
    get_settings.cache_clear()


def test_quality_gate_returns_422(client, monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(
        "services.api.services.backtests.data_status",
        lambda *_a, **_k: {"ready": True, "corporate_actions_verified": True, "manifest": {}},
    )

    def boom(_root):
        raise HTTPException(
            status_code=422,
            detail={"code": "data_quality", "message": "行情数据质量校验未通过，拒绝开跑回测。"},
        )

    monkeypatch.setattr("services.api.services.backtests._quality_gate", boom)
    strategy = _strategy(client)
    res = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": strategy["latest_version"]["id"],
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "data_quality"


def test_missing_data_returns_409(client, monkeypatch):
    monkeypatch.setattr(
        "services.api.services.backtests.data_status",
        lambda *_a, **_k: {"ready": False, "manifest": {}},
    )
    strategy = _strategy(client)
    res = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": strategy["latest_version"]["id"],
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
        },
    )
    assert res.status_code == 409


def test_stooq_snapshot_blocks_adjusted_backtest(client, monkeypatch):
    monkeypatch.setattr(
        "services.api.services.backtests.data_status",
        lambda *_a, **_k: {
            "ready": True,
            "corporate_actions_verified": False,
            "manifest": {"source": "stooq"},
        },
    )
    monkeypatch.setattr("services.api.services.backtests._quality_gate", lambda *_a, **_k: None)
    strategy = _strategy(client)
    res = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": strategy["latest_version"]["id"],
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "provider_capability"


def test_backtest_logs_endpoint(client, monkeypatch):
    _ready(monkeypatch)
    strategy = _strategy(client)
    created = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": strategy["latest_version"]["id"],
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
        },
    ).json()
    logs = client.get(f"/api/v1/backtests/{created['id']}/logs")
    assert logs.status_code == 200
    assert "stdout" in logs.json()


def test_duplicate_parameter_hash(client, monkeypatch):
    _ready(monkeypatch)
    strategy = _strategy(client)
    body = {
        "strategy_version_id": strategy["latest_version"]["id"],
        "start_date": "2018-01-01",
        "end_date": "2018-06-01",
        "parameters": {"lookback": 200},
    }
    assert client.post("/api/v1/backtests", json=body).status_code == 201
    # bump inflight limit so the duplicate submission is accepted
    from services.api.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AXIOM_MAX_INFLIGHT_BACKTESTS", "10")
    get_settings.cache_clear()
    assert client.post("/api/v1/backtests", json=body).status_code == 201
    stats = client.get(f"/api/v1/strategies/{strategy['id']}/trial-stats").json()
    assert stats["total_trials"] == 2
    assert stats["by_snapshot"][0]["duplicate_parameter_hashes"] >= 1
    get_settings.cache_clear()
