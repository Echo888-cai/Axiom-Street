"""P2.2 acceptance: unified task read model + explicit cancel semantics.

Covers: aggregation of backtest/validation/ingest/copilot into one shape,
newest-first ordering, backtest cancel delegation (real terminal state) and
explicit "not cancelable / unknown" semantics.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _empty_db():
    from services.api import models as _models  # noqa: F401
    from services.api.db import Base

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_tasks_read_model_aggregates_kinds():
    from datetime import date

    from services.api.models import (
        Backtest,
        BacktestStatus,
        CopilotInsight,
        CopilotInsightStatus,
        IngestJob,
        IngestJobStatus,
        Strategy,
        StrategyStatus,
        StrategyVersion,
        ValidationKind,
        ValidationRun,
        ValidationRunStatus,
    )
    from services.api.services.tasks import list_tasks

    db = _empty_db()
    strategy = Strategy(name="任务中心", status=StrategyStatus.BACKTESTED)
    db.add(strategy)
    db.flush()
    version = StrategyVersion(
        strategy_id=strategy.id, version=1, code="pass", config={}, created_by="local"
    )
    db.add(version)
    db.flush()
    base = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)
    db.add(
        Backtest(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            strategy_version_id=version.id,
            start_date=date(2018, 1, 1),
            end_date=date(2018, 6, 1),
            status=BacktestStatus.QUEUED,
            progress_step="Queued",
            created_at=base,
        )
    )
    db.add(
        ValidationRun(
            id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            strategy_id=strategy.id,
            strategy_version_id=version.id,
            kind=ValidationKind.PBO,
            status=ValidationRunStatus.RUNNING,
            params={},
            result={},
            created_at=base.replace(minute=1),
        )
    )
    db.add(
        IngestJob(
            id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
            status=IngestJobStatus.COMPLETED,
            symbols=["SPY", "QQQ"],
            mode="full",
            created_at=base.replace(minute=2),
        )
    )
    db.add(
        CopilotInsight(
            id=uuid.UUID("00000000-0000-0000-0000-000000000004"),
            strategy_id=strategy.id,
            status=CopilotInsightStatus.DONE,
            narrative="x",
            created_at=base.replace(minute=3),
        )
    )
    db.commit()

    tasks = list_tasks(db)
    kinds = [t.kind for t in tasks]
    assert kinds == ["copilot", "ingest", "validation", "backtest"]  # 按 created_at 倒序

    by_id = {t.id: t for t in tasks}
    bt = by_id[uuid.UUID("00000000-0000-0000-0000-000000000001")]
    assert bt.kind == "backtest" and bt.cancelable is True
    assert bt.strategy_name == "任务中心"
    assert bt.ref == f"/backtests/{bt.id}"
    val = by_id[uuid.UUID("00000000-0000-0000-0000-000000000002")]
    assert val.kind == "validation" and val.cancelable is False
    assert "PBO" in val.title
    ing = by_id[uuid.UUID("00000000-0000-0000-0000-000000000003")]
    assert ing.kind == "ingest" and "SPY, QQQ" in ing.title


def test_tasks_api_backtest_list_and_cancel(client):
    created = client.post("/api/v1/strategies", json={"name": "任务中心"})
    assert created.status_code == 201

    bt = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": created.json()["latest_version"]["id"],
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
            "benchmark": "SPY",
            "initial_capital": 100000,
        },
    )
    assert bt.status_code in (200, 201), bt.text
    backtest_id = bt.json()["id"]

    tasks = client.get("/api/v1/tasks")
    assert tasks.status_code == 200
    items = tasks.json()
    assert any(t["kind"] == "backtest" and t["cancelable"] for t in items)

    single = client.get(f"/api/v1/tasks/{backtest_id}")
    assert single.status_code == 200
    assert single.json()["kind"] == "backtest"

    cancelled = client.post(f"/api/v1/tasks/{backtest_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"

    # 再取消一次：终态 no-op → 409 语义明确
    again = client.post(f"/api/v1/tasks/{backtest_id}/cancel")
    assert again.status_code == 409


def test_tasks_api_unknown_and_unsupported_cancel(client):
    unknown = client.post(f"/api/v1/tasks/{uuid.uuid4()}/cancel")
    assert unknown.status_code == 404
