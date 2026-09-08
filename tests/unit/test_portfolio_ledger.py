"""Portfolio and attribution ledger schema tests (E8-1)."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.db import Base
from services.api.models import (
    Portfolio,
    PortfolioAllocation,
    PortfolioAttribution,
    PortfolioStatus,
    Strategy,
)


def test_portfolio_ledger_persists_configuration_and_snapshot() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    strategy_id = uuid4()
    with Session(engine) as db:
        db.add(Strategy(id=strategy_id, name="Portfolio strategy", benchmark="SPY"))
        portfolio = Portfolio(
            name="Research portfolio",
            base_currency="USD",
            status=PortfolioStatus.ACTIVE,
            initial_capital=100_000,
        )
        db.add(portfolio)
        db.flush()
        allocation = PortfolioAllocation(
            portfolio_id=portfolio.id,
            strategy_id=strategy_id,
            weight=1.0,
            effective_from=date(2026, 1, 1),
        )
        snapshot = PortfolioAttribution(
            portfolio_id=portfolio.id,
            as_of=date(2026, 9, 8),
            portfolio_return=0.1,
            benchmark_return=0.05,
            allocation_effect=0.0,
            selection_effect=0.05,
            interaction_effect=0.0,
            active_return=0.05,
            inputs={"strategies": {str(strategy_id): {"return": 0.1}}},
        )
        db.add_all([allocation, snapshot])
        db.commit()

        assert db.get(Portfolio, portfolio.id).status is PortfolioStatus.ACTIVE
        assert db.get(PortfolioAttribution, snapshot.id).active_return == pytest.approx(0.05)


def test_portfolio_allocation_and_snapshot_keys_are_unique() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        strategy = Strategy(name="Portfolio strategy", benchmark="SPY")
        portfolio = Portfolio(
            name="Research portfolio", base_currency="USD", initial_capital=100_000
        )
        db.add_all([strategy, portfolio])
        db.flush()
        db.add(
            PortfolioAllocation(
                portfolio_id=portfolio.id,
                strategy_id=strategy.id,
                weight=1.0,
                effective_from=date(2026, 1, 1),
            )
        )
        db.commit()
        db.add(
            PortfolioAllocation(
                portfolio_id=portfolio.id,
                strategy_id=strategy.id,
                weight=1.0,
                effective_from=date(2026, 1, 1),
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
