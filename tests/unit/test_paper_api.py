"""Paper execution HTTP contract tests (E6-1)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from services.api import db as db_module
from services.api.models import PaperOrder, PaperOrderSide, PaperOrderStatus, Strategy


def _seed_strategy():
    with db_module.SessionLocal() as db:
        strategy = Strategy(id=uuid4(), name="API paper strategy", benchmark="SPY")
        strategy_id = strategy.id
        db.add(strategy)
        db.commit()
        return strategy_id


def test_paper_order_rejects_non_positive_quantity(client) -> None:
    response = client.post(
        "/api/v1/paper/orders",
        json={
            "strategy_id": str(uuid4()),
            "symbol": "SPY",
            "side": "BUY",
            "quantity": 0,
            "simulation_price": 100,
            "client_order_id": "api-1",
        },
    )

    assert response.status_code == 422


def test_paper_order_requires_existing_strategy(client) -> None:
    response = client.post(
        "/api/v1/paper/orders",
        json={
            "strategy_id": str(uuid4()),
            "symbol": "SPY",
            "side": "BUY",
            "quantity": 1,
            "simulation_price": 100,
            "client_order_id": "api-2",
        },
    )

    assert response.status_code == 404


def test_paper_order_enqueues_without_accepting_client_risk_state(client, monkeypatch) -> None:
    strategy_id = _seed_strategy()
    captured: list[dict] = []

    def delay(payload: dict) -> None:
        captured.append(payload)

    monkeypatch.setattr("services.worker.tasks.run_paper_order_task", SimpleNamespace(delay=delay))
    response = client.post(
        "/api/v1/paper/orders",
        json={
            "strategy_id": str(strategy_id),
            "symbol": " spy ",
            "side": "buy",
            "quantity": 1,
            "simulation_price": 100,
            "client_order_id": " api-3 ",
            "risk_limits": {"max_position_pct": 1},
            "gross_exposure": 0,
        },
    )

    assert response.status_code == 202
    assert response.json() == {"status": "queued"}
    assert captured == [
        {
            "strategy_id": str(strategy_id),
            "symbol": "SPY",
            "side": "BUY",
            "quantity": 1.0,
            "simulation_price": 100.0,
            "client_order_id": "api-3",
        }
    ]


def test_paper_order_and_reconciliation_queries_are_strategy_scoped(client) -> None:
    strategy_id = _seed_strategy()
    with db_module.SessionLocal() as db:
        order = PaperOrder(
            strategy_id=strategy_id,
            client_order_id="api-4",
            symbol="SPY",
            side=PaperOrderSide.BUY,
            requested_quantity=1,
            simulation_price=100,
            status=PaperOrderStatus.QUEUED,
        )
        db.add(order)
        db.commit()

    orders = client.get(f"/api/v1/paper/orders?strategy_id={strategy_id}")
    positions = client.get(f"/api/v1/paper/positions?strategy_id={strategy_id}")
    reconciliation = client.get(f"/api/v1/paper/reconciliation?strategy_id={strategy_id}")

    assert orders.status_code == 200
    assert orders.json()[0]["client_order_id"] == "api-4"
    assert positions.status_code == 200
    assert positions.json()["positions"] == []
    assert reconciliation.status_code == 200
    assert reconciliation.json() is None
