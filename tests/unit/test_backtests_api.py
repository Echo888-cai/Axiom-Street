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
            "symbols": ["SPY"],
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
    snapshot = created.json()["universe_snapshot"]
    assert snapshot is not None
    assert snapshot[0]["symbol"] == "SPY"
    assert snapshot[0]["effective_to"] is None
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
    monkeypatch.setenv("STREET_MAX_INFLIGHT_BACKTESTS", "1")
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

    def boom(_root, symbols=None):
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
    # bump inflight limit so the forced duplicate is accepted
    from services.api.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("STREET_MAX_INFLIGHT_BACKTESTS", "10")
    get_settings.cache_clear()
    assert client.post("/api/v1/backtests", json={**body, "force": True}).status_code == 201
    stats = client.get(f"/api/v1/strategies/{strategy['id']}/trial-stats").json()
    assert stats["total_trials"] == 2
    assert stats["by_snapshot"][0]["duplicate_parameter_hashes"] >= 1
    get_settings.cache_clear()


def test_identical_backtest_hits_cache_without_new_trial(client, monkeypatch):
    _ready(monkeypatch)
    from services.api.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("STREET_MAX_INFLIGHT_BACKTESTS", "10")
    get_settings.cache_clear()
    strategy = _strategy(client)
    body = {
        "strategy_version_id": strategy["latest_version"]["id"],
        "start_date": "2018-01-01",
        "end_date": "2018-06-01",
    }
    first = client.post("/api/v1/backtests", json=body)
    assert first.status_code == 201, first.text
    assert first.json()["cache_hit"] is False
    second = client.post("/api/v1/backtests", json=body)
    assert second.status_code == 201, second.text
    assert second.json()["cache_hit"] is True
    assert second.json()["id"] == first.json()["id"]
    stats = client.get(f"/api/v1/strategies/{strategy['id']}/trial-stats").json()
    assert stats["total_trials"] == 1
    listed = client.get("/api/v1/backtests").json()
    assert listed["total"] == 1
    forced = client.post("/api/v1/backtests", json={**body, "force": True})
    assert forced.status_code == 201
    assert forced.json()["cache_hit"] is False
    assert forced.json()["id"] != first.json()["id"]
    stats = client.get(f"/api/v1/strategies/{strategy['id']}/trial-stats").json()
    assert stats["total_trials"] == 2
    get_settings.cache_clear()


def _seed_completed_backtest(client, *, name: str, metrics: dict | None = None) -> str:
    """Insert a COMPLETED backtest with three equity points and optional metrics rows.

    Runs on the same in-memory database the `client` fixture patches into
    services.api.db.SessionLocal.
    """
    from datetime import date, datetime, timezone
    from uuid import uuid4

    from services.api import db as db_module
    from services.api.models import (
        Backtest,
        BacktestEquity,
        BacktestMetrics,
        BacktestStatus,
        Strategy,
        StrategyStatus,
        StrategyVersion,
    )

    db = db_module.SessionLocal()
    try:
        strategy = Strategy(name=name, status=StrategyStatus.BACKTESTED)
        db.add(strategy)
        db.flush()
        strategy.family_id = strategy.id
        version = StrategyVersion(strategy_id=strategy.id, version=1, code="print(1)", config={})
        db.add(version)
        db.flush()
        backtest = Backtest(
            id=uuid4(),
            strategy_version_id=version.id,
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 31),
            status=BacktestStatus.COMPLETED,
            universe_snapshot=[],
        )
        db.add(backtest)
        db.flush()
        for i, value in enumerate((100_000.0, 101_000.0, 102_000.0)):
            day = (date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 6))[i]
            db.add(
                BacktestEquity(
                    backtest_id=backtest.id,
                    ts=datetime(day.year, day.month, day.day, tzinfo=timezone.utc),
                    strategy_value=value,
                )
            )
        if metrics is not None:
            db.add(BacktestMetrics(backtest_id=backtest.id, **metrics))
        return str(backtest.id)
    finally:
        db.commit()
        db.close()


def test_compare_equity_is_get_only(client, monkeypatch):
    """RC-W4 drift fix: the shipped frontend called POST; the contract is GET-only."""
    _ready(monkeypatch)
    a = _seed_completed_backtest(client, name="alpha")
    b = _seed_completed_backtest(client, name="beta")
    res = client.post(f"/api/v1/backtests/compare/equity?ids={a}&ids={b}")
    assert res.status_code == 405


def test_compare_equity_returns_series_with_metrics(client, monkeypatch):
    _ready(monkeypatch)
    a = _seed_completed_backtest(
        client,
        name="alpha",
        metrics={
            "final_equity": 102_000.0,
            "total_return": 0.02,
            "cagr": 0.12,
            "sharpe": 1.5,
            "max_drawdown": -0.2,
            "volatility": 0.15,
            "trade_count": 42,
        },
    )
    b = _seed_completed_backtest(client, name="beta")
    res = client.get(f"/api/v1/backtests/compare/equity?ids={a}&ids={b}")
    assert res.status_code == 200, res.text
    series = res.json()["series"]
    assert [s["label"] for s in series] == ["alpha v1", "beta v1"]
    assert series[0]["metrics"] == {
        "final_equity": 102_000.0,
        "total_return": 0.02,
        "cagr": 0.12,
        "sharpe": 1.5,
        "max_drawdown": -0.2,
        "volatility": 0.15,
        "trade_count": 42,
    }
    assert series[1]["metrics"] is None
    assert series[0]["data"][0]["value"] == 100_000.0
    assert series[0]["data"][-1]["value"] == 102_000.0


def test_compare_equity_normalized_and_arity_guard(client, monkeypatch):
    _ready(monkeypatch)
    a = _seed_completed_backtest(client, name="alpha")
    b = _seed_completed_backtest(client, name="beta")
    res = client.get(f"/api/v1/backtests/compare/equity?ids={a}&ids={b}&normalized=true")
    assert res.status_code == 200
    data = res.json()["series"][0]["data"]
    assert data[0]["value"] == 100
    assert abs(data[-1]["value"] - 102) < 1e-9
    single = client.get(f"/api/v1/backtests/compare/equity?ids={a}")
    assert single.status_code == 422
