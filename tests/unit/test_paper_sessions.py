"""P5 acceptance: market clock/session with idempotent bars and orders, halt and
kill switch that never auto-liquidate, reconciliation that explains discrepancies,
and an honest observation-progress report (30 days, with executions).
"""

from __future__ import annotations

from datetime import date


def _strategy(client) -> dict:
    res = client.post("/api/v1/strategies", json={"name": "P5"})
    assert res.status_code == 201, res.text
    return res.json()


def _session(client, strategy: dict, **extra) -> dict:
    res = client.post(
        "/api/v1/paper-sessions",
        json={"strategy_id": strategy["id"], "initial_cash": 100_000, **extra},
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_duplicate_bar_never_creates_a_second_order(client):
    strategy = _session(client, _strategy(client))
    signals = [{"symbol": "SPY", "signal": "BUY", "quantity": 10}]
    first = client.post(
        f"/api/v1/paper-sessions/{strategy['id']}/bars",
        json={"bar_date": "2026-01-05", "signals": signals, "prices": {"SPY": 100}},
    ).json()
    assert first["events"][0]["status"] == "EXECUTED"
    assert first["events"][0]["order"] is not None

    replay = client.post(
        f"/api/v1/paper-sessions/{strategy['id']}/bars",
        json={"bar_date": "2026-01-05", "signals": signals, "prices": {"SPY": 100}},
    ).json()
    assert replay["events"][0]["status"] == "DUPLICATE_BAR"
    assert replay["events"][0]["order"] is None
    assert "不重复下单" in replay["events"][0]["reason"]


def test_late_or_revised_bar_is_blocked_by_policy(client):
    session = _session(client, _strategy(client))
    client.post(
        f"/api/v1/paper-sessions/{session['id']}/bars",
        json={
            "bar_date": "2026-01-06",
            "signals": [{"symbol": "SPY", "signal": "BUY", "quantity": 10}],
        },
    )
    late = client.post(
        f"/api/v1/paper-sessions/{session['id']}/bars",
        json={
            "bar_date": "2026-01-05",
            "signals": [{"symbol": "SPY", "signal": "BUY", "quantity": 99}],
        },
    ).json()
    assert late["events"][0]["status"] == "REVISION_BLOCKED"
    assert "迟到/修订" in late["events"][0]["reason"]
    assert late["events"][0]["order"] is None


def test_idempotency_key_replays_same_order(client):
    from services.api.services.paper_session import _place_order

    session = _session(client, _strategy(client))
    from services.api import db as db_module

    db = db_module.SessionLocal()
    try:
        row = db.get(
            __import__("services.api.models", fromlist=["PaperSession"]).PaperSession,
            __import__("uuid", fromlist=["UUID"]).UUID(session["id"]),
        )
        first = _place_order(
            db, row, symbol="AAPL", side="BUY", quantity=5, price=200.0, bar_date=date(2026, 1, 6)
        )
        second = _place_order(
            db, row, symbol="AAPL", side="BUY", quantity=5, price=200.0, bar_date=date(2026, 1, 6)
        )
        assert first["order_id"] == second["order_id"]
    finally:
        db.close()


def test_halt_and_kill_switch_block_risk_but_do_not_liquidate(client):
    session = _session(client, _strategy(client))
    halted = client.post(f"/api/v1/paper-sessions/{session['id']}/halt").json()
    assert halted["status"] == "HALTED"
    blocked = client.post(
        f"/api/v1/paper-sessions/{session['id']}/bars",
        json={
            "bar_date": "2026-01-07",
            "signals": [{"symbol": "SPY", "signal": "BUY", "quantity": 10}],
        },
    ).json()
    assert blocked["events"][0]["status"] == "RISK_BLOCKED"
    assert "不自动平仓" in blocked["events"][0]["reason"]

    resumed = client.post(f"/api/v1/paper-sessions/{session['id']}/resume").json()
    assert resumed["status"] == "ACTIVE"

    killed = client.post(f"/api/v1/paper-sessions/{session['id']}/kill-switch?enabled=true").json()
    assert killed["kill_switch"] is True
    killed_bar = client.post(
        f"/api/v1/paper-sessions/{session['id']}/bars",
        json={
            "bar_date": "2026-01-08",
            "signals": [{"symbol": "SPY", "signal": "BUY", "quantity": 10}],
        },
    ).json()
    assert killed_bar["events"][0]["status"] == "RISK_BLOCKED"


def test_reconcile_explains_discrepancies(client):
    session = _session(client, _strategy(client))
    out = client.post(f"/api/v1/paper-sessions/{session['id']}/reconcile").json()
    assert out["explained"] is True
    assert out["discrepancy"] == 0.0


def test_observation_status_is_honest_and_reaches_target(client):
    session = _session(client, _strategy(client))
    status_before = client.get(f"/api/v1/paper-sessions/{session['id']}/observation-status").json()
    assert status_before["sufficient"] is False
    assert "未达 30" in status_before["note"]

    for idx in range(30):
        day = date(2026, 1, 1 + idx)
        client.post(
            f"/api/v1/paper-sessions/{session['id']}/bars",
            json={
                "bar_date": day.isoformat(),
                "signals": [{"symbol": "SPY", "signal": "BUY", "quantity": 1 + idx}],
            },
        )
    status_after = client.get(f"/api/v1/paper-sessions/{session['id']}/observation-status").json()
    assert status_after["observation_days"] == 30
    assert status_after["executed_signals"] == 30
    assert status_after["sufficient"] is True
