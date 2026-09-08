"""Risk summary HTTP contract tests."""

from __future__ import annotations

from uuid import uuid4

from services.api import db as db_module
from services.api.models import (
    PaperAccount,
    PaperPosition,
    PaperReconciliation,
    PaperReconciliationStatus,
    Strategy,
    StrategyStatus,
    StrategyVersion,
)


def _seed_strategy(*, with_account: bool = True) -> tuple[str, str]:
    with db_module.SessionLocal() as db:
        strategy = Strategy(
            id=uuid4(),
            name="Risk summary strategy",
            benchmark="SPY",
            status=StrategyStatus.PAPER,
        )
        version = StrategyVersion(
            id=uuid4(),
            strategy_id=strategy.id,
            version=1,
            code="class Strategy: pass",
            config={"risk_limits": {"max_gross_leverage": 1.5}},
        )
        db.add_all([strategy, version])
        if with_account:
            db.add_all(
                [
                    PaperAccount(
                        strategy_id=strategy.id,
                        initial_capital=100_000,
                        cash=70_000,
                    ),
                    PaperPosition(
                        strategy_id=strategy.id,
                        symbol="SPY",
                        quantity=100,
                        average_price=200,
                        realized_pnl=0,
                        mark_price=200,
                    ),
                    PaperReconciliation(
                        strategy_id=strategy.id,
                        status=PaperReconciliationStatus.MATCHED,
                        expected_positions={},
                        actual_positions={},
                        differences={},
                    ),
                ]
            )
        db.commit()
        return str(strategy.id), str(version.id)


def test_risk_summary_returns_server_owned_account_and_exposure(client) -> None:
    strategy_id, _ = _seed_strategy()

    response = client.get(f"/api/v1/risk/summary?strategy_id={strategy_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["strategy_status"] == "PAPER"
    assert body["risk_config_valid"] is True
    assert body["account_available"] is True
    assert body["equity"] == 90_000
    assert body["gross_exposure"] == 20_000 / 90_000
    assert body["reconciliation_status"] == "MATCHED"
    assert body["blocking_reasons"] == []


def test_risk_summary_explains_unavailable_paper_state(client) -> None:
    strategy_id, _ = _seed_strategy(with_account=False)

    response = client.get(f"/api/v1/risk/summary?strategy_id={strategy_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["account_available"] is False
    assert body["equity"] is None
    assert "paper_account_missing" in body["blocking_reasons"]
    assert "paper_reconciliation_not_matched" in body["blocking_reasons"]


def test_risk_summary_requires_existing_strategy(client) -> None:
    response = client.get(f"/api/v1/risk/summary?strategy_id={uuid4()}")

    assert response.status_code == 404
