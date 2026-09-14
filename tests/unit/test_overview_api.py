from datetime import date, datetime, timezone
from uuid import UUID

from services.api import db as db_module
from services.api.models import Backtest, BacktestMetrics, BacktestStatus, Strategy, StrategyStatus


def test_overview_counts_entire_database_not_first_page(client):
    with db_module.SessionLocal() as db:
        db.add_all(
            [
                Strategy(
                    name=f"Research {i}",
                    status=(
                        StrategyStatus.DRAFT
                        if i < 100
                        else StrategyStatus.BACKTESTED
                        if i < 130
                        else StrategyStatus.VALIDATED
                    ),
                )
                for i in range(137)
            ]
        )
        db.commit()
    assert len(client.get("/api/v1/strategies").json()["items"]) == 100
    response = client.get("/api/v1/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["strategy_count"] == 137
    assert body["strategy_counts_by_status"]["DRAFT"] == 100
    assert body["strategy_counts_by_status"]["BACKTESTED"] == 30
    assert body["strategy_counts_by_status"]["VALIDATED"] == 7
    assert body["strategy_counts_by_status"]["LIVE"] == 0
    assert sum(body["strategy_counts_by_status"].values()) == 137
    assert body["latest_completed_backtest"] is None
    assert datetime.fromisoformat(body["as_of"].replace("Z", "+00:00")).tzinfo is not None


def test_overview_empty_database_returns_explicit_empty_state(client):
    response = client.get("/api/v1/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["strategy_count"] == 0
    assert all(n == 0 for n in body["strategy_counts_by_status"].values())
    assert body["latest_completed_backtest"] is None


def test_overview_reads_latest_completion_even_behind_backtest_page(client):
    strategy = client.post("/api/v1/strategies", json={"name": "Reference"}).json()
    version_id = UUID(strategy["latest_version"]["id"])
    finished = datetime(2026, 9, 13, tzinfo=timezone.utc)
    with db_module.SessionLocal() as db:
        for i in range(1, 63):
            db.add(
                Backtest(
                    id=UUID(int=i),
                    strategy_version_id=version_id,
                    start_date=date(2020, 1, 1),
                    end_date=date(2021, 1, 1),
                    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    status=BacktestStatus.COMPLETED if i <= 2 else BacktestStatus.FAILED,
                    finished_at=finished,
                )
            )
        db.add(BacktestMetrics(backtest_id=UUID(int=2), total_return=0.0, sharpe=0.2))
        db.commit()
    response = client.get("/api/v1/overview")
    assert response.status_code == 200
    latest = response.json()["latest_completed_backtest"]
    assert latest["id"] == str(UUID(int=2))
    assert latest["strategy_name"] == "Reference"
    assert latest["total_return"] == 0.0
    assert latest["sharpe"] == 0.2


def test_overview_reflects_create_and_delete(client):
    strategy = client.post("/api/v1/strategies", json={"name": "Temporary"}).json()
    response = client.get("/api/v1/overview")
    assert response.status_code == 200
    assert response.json()["strategy_count"] == 1
    assert client.delete(f"/api/v1/strategies/{strategy['id']}").status_code == 204
    assert client.get("/api/v1/overview").json()["strategy_count"] == 0


def test_deleting_researched_strategy_is_rejected_without_losing_history(client):
    strategy = client.post("/api/v1/strategies", json={"name": "Keep evidence"}).json()
    version_id = UUID(strategy["latest_version"]["id"])
    with db_module.SessionLocal() as db:
        db.add(
            Backtest(
                strategy_version_id=version_id,
                start_date=date(2020, 1, 1),
                end_date=date(2021, 1, 1),
                status=BacktestStatus.COMPLETED,
            )
        )
        db.commit()
    response = client.delete(f"/api/v1/strategies/{strategy['id']}")
    assert response.status_code == 409
    assert client.get(f"/api/v1/strategies/{strategy['id']}").status_code == 200
