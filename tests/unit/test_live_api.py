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


def test_live_activation_is_a_fail_closed_no_side_effect_guard(client) -> None:
    strategy_id = _seed_strategy()

    response = client.post("/api/v1/live/activate", json={"strategy_id": str(strategy_id)})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "live_not_ready"
    assert "live_broker_unavailable" in detail["reasons"]
