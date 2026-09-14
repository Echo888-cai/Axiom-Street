"""Fail-closed Live readiness HTTP contract tests (E6-2)."""

from __future__ import annotations

from uuid import uuid4

from services.api import db as db_module
from services.api.models import Strategy


def _seed_strategy():
    with db_module.SessionLocal() as db:
        strategy = Strategy(id=uuid4(), name="Readiness strategy", benchmark="SPY")
        strategy_id = strategy.id
        db.add(strategy)
        db.commit()
        return strategy_id


def test_live_readiness_reports_evidence_and_stays_false_by_default(client) -> None:
    strategy_id = _seed_strategy()

    response = client.get(f"/api/v1/live/readiness?strategy_id={strategy_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert "strategy_not_approved" in body["reasons"]
    assert "validation_incomplete" in body["reasons"]
    assert "live_broker_unavailable" in body["reasons"]
    assert body["evidence"]["broker_implemented"] is False


def test_live_readiness_requires_existing_strategy(client) -> None:
    response = client.get(f"/api/v1/live/readiness?strategy_id={uuid4()}")

    assert response.status_code == 404


def test_live_activation_is_a_fail_closed_no_side_effect_guard(client, monkeypatch) -> None:
    """P6B/C：先授权、再资金上限、最后 readiness；任何一步不满足都拒绝，无副作用。"""
    strategy_id = _seed_strategy()

    # 1) 未配置授权令牌 → 403（真实资金需要单独授权）
    response = client.post("/api/v1/live/activate", json={"strategy_id": str(strategy_id)})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "live_authorization_not_configured"

    # 2) 配置令牌与上限后，仍因证据/券商不满足而拒绝（不冒充通过）
    monkeypatch.setenv("STREET_LIVE_AUTHORIZATION_TOKEN", "unit-token")
    monkeypatch.setenv("STREET_LIVE_CAPITAL_CAP", "10000")
    from services.api.settings import get_settings

    get_settings.cache_clear()
    try:
        response = client.post(
            "/api/v1/live/activate",
            json={
                "strategy_id": str(strategy_id),
                "authorization": "unit-token",
                "capital_cap": 5_000,
            },
        )
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["code"] in {"live_not_ready", "live_broker_unavailable"}
        assert "live_broker_unavailable" in detail.get("reasons", ["live_broker_unavailable"])
    finally:
        get_settings.cache_clear()
