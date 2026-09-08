"""Paper execution ledger schema tests (E6-1)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.db import Base
from services.api.models import (
    PaperAccount,
    PaperFill,
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    PaperPosition,
    PaperReconciliation,
    PaperReconciliationStatus,
    Strategy,
    StrategyStatus,
    StrategyVersion,
)


def test_paper_ledger_persists_account_order_fill_position_and_reconciliation() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    strategy_id = uuid.uuid4()
    with Session(engine) as db:
        strategy = Strategy(
            id=strategy_id,
            name="paper strategy",
            status=StrategyStatus.VALIDATED,
            asset_class="equity",
            benchmark="SPY",
        )
        version = StrategyVersion(
            strategy_id=strategy_id,
            version=1,
            code="class Strategy: pass",
            config={"risk_limits": {"max_position_pct": 0.5}},
        )
        db.add_all([strategy, version])
        db.flush()
        account = PaperAccount(strategy_id=strategy_id, initial_capital=1000, cash=1000)
        order = PaperOrder(
            strategy_id=strategy_id,
            strategy_version_id=version.id,
            client_order_id="paper-1",
            symbol="SPY",
            side=PaperOrderSide.BUY,
            requested_quantity=5,
            filled_quantity=5,
            simulation_price=100,
            status=PaperOrderStatus.FILLED,
        )
        db.add_all([account, order])
        db.flush()
        fill = PaperFill(
            order_id=order.id,
            strategy_id=strategy_id,
            symbol="SPY",
            side=PaperOrderSide.BUY,
            quantity=5,
            price=100,
            fee=0,
        )
        position = PaperPosition(
            strategy_id=strategy_id,
            symbol="SPY",
            quantity=5,
            average_price=100,
            realized_pnl=0,
            mark_price=100,
        )
        reconciliation = PaperReconciliation(
            strategy_id=strategy_id,
            status=PaperReconciliationStatus.MATCHED,
            expected_positions={"SPY": {"quantity": 5}},
            actual_positions={"SPY": {"quantity": 5}},
            differences={},
        )
        db.add_all([fill, position, reconciliation])
        db.commit()

        assert db.get(PaperOrder, order.id).status is PaperOrderStatus.FILLED
        assert db.get(PaperPosition, position.id).symbol == "SPY"


def test_client_order_id_is_unique_per_strategy() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    strategy_id = uuid.uuid4()
    with Session(engine) as db:
        db.add(
            Strategy(
                id=strategy_id,
                name="paper strategy",
                status=StrategyStatus.VALIDATED,
                asset_class="equity",
                benchmark="SPY",
            )
        )
        db.add(
            PaperOrder(
                strategy_id=strategy_id,
                client_order_id="same-key",
                symbol="SPY",
                side=PaperOrderSide.BUY,
                requested_quantity=1,
                simulation_price=100,
                status=PaperOrderStatus.QUEUED,
            )
        )
        db.commit()
        db.add(
            PaperOrder(
                strategy_id=strategy_id,
                client_order_id="same-key",
                symbol="QQQ",
                side=PaperOrderSide.BUY,
                requested_quantity=1,
                simulation_price=100,
                status=PaperOrderStatus.QUEUED,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
