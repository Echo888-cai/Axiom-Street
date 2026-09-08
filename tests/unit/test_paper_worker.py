"""Paper worker transaction and idempotency tests (E6-1)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api import db as db_module
from services.api.db import Base
from services.api.models import (
    PaperAccount,
    PaperFill,
    PaperOrder,
    PaperOrderStatus,
    PaperPosition,
    PaperReconciliationStatus,
    Strategy,
    StrategyStatus,
    StrategyVersion,
)
from services.worker.tasks.paper import execute_paper_order


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(db_module, "SessionLocal", SessionLocal)
    monkeypatch.setattr("services.worker.tasks.SessionLocal", SessionLocal)
    return SessionLocal


def _seed_strategy(SessionLocal, *, risk_limits: dict) -> Strategy:
    with SessionLocal() as db:
        strategy = Strategy(
            id=uuid4(),
            name="Paper strategy",
            status=StrategyStatus.VALIDATED,
            benchmark="SPY",
        )
        db.add(strategy)
        db.flush()
        db.add(
            StrategyVersion(
                strategy_id=strategy.id,
                version=1,
                code="class Strategy: pass",
                config={"risk_limits": risk_limits},
            )
        )
        strategy_id = strategy.id
        db.commit()
        return strategy_id


def _payload(strategy_id, **overrides):
    payload = {
        "strategy_id": str(strategy_id),
        "symbol": "spy",
        "side": "BUY",
        "quantity": 100,
        "simulation_price": 100,
        "client_order_id": "paper-1",
    }
    payload.update(overrides)
    return payload


def test_worker_risk_gates_fill_and_reconciles_position(db_session) -> None:
    strategy_id = _seed_strategy(db_session, risk_limits={"max_position_pct": 0.05})

    result = execute_paper_order(_payload(strategy_id))

    assert result["status"] == "filled"
    with db_session() as db:
        order = db.scalar(select(PaperOrder))
        fill = db.scalar(select(PaperFill))
        position = db.scalar(select(PaperPosition))
        assert order.status is PaperOrderStatus.FILLED
        assert order.filled_quantity == pytest.approx(50)
        assert fill.quantity == pytest.approx(50)
        assert position.quantity == pytest.approx(50)
        assert position.average_price == pytest.approx(100)
        account = db.scalar(select(PaperAccount))
        assert account.cash == pytest.approx(95000)
        reconciliation = result["reconciliation"]
        assert reconciliation["status"] == PaperReconciliationStatus.MATCHED.value


def test_rejected_oversell_does_not_create_a_fill(db_session) -> None:
    strategy_id = _seed_strategy(db_session, risk_limits={})
    execute_paper_order(_payload(strategy_id, quantity=2))

    result = execute_paper_order(
        _payload(strategy_id, side="SELL", quantity=3, client_order_id="paper-2")
    )

    assert result["status"] == "rejected"
    with db_session() as db:
        assert db.scalar(select(func.count(PaperFill.id))) == 1
        rejected = db.scalar(select(PaperOrder).where(PaperOrder.client_order_id == "paper-2"))
        assert rejected.status is PaperOrderStatus.REJECTED


def test_duplicate_client_order_is_idempotent(db_session) -> None:
    strategy_id = _seed_strategy(db_session, risk_limits={})
    first = execute_paper_order(_payload(strategy_id))
    second = execute_paper_order(_payload(strategy_id))

    assert first["status"] == "filled"
    assert second["status"] == "duplicate"
    with db_session() as db:
        assert db.scalar(select(func.count(PaperOrder.id))) == 1
        assert db.scalar(select(func.count(PaperFill.id))) == 1


def test_invalid_server_risk_config_fails_without_fill(db_session) -> None:
    strategy_id = _seed_strategy(db_session, risk_limits={"max_position_pct": "not-a-number"})

    result = execute_paper_order(_payload(strategy_id))

    assert result["status"] == "failed"
    with db_session() as db:
        order = db.scalar(select(PaperOrder))
        assert order.status is PaperOrderStatus.FAILED
        assert db.scalar(select(func.count(PaperFill.id))) == 0
