from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from services.api.models import Backtest, BacktestStatus, Strategy, StrategyStatus, StrategyVersion
from services.worker.tasks import reconcile_orphan_backtests


def test_orphan_reconcile_fails_stale_running(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from services.api import db as db_module
    from services.api.db import Base

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(db_module, "SessionLocal", Session)
    monkeypatch.setattr("services.worker.tasks.SessionLocal", Session)

    db = Session()
    strategy = Strategy(name="s", status=StrategyStatus.DRAFT)
    db.add(strategy)
    db.flush()
    version = StrategyVersion(strategy_id=strategy.id, version=1, code="x", config={})
    db.add(version)
    db.flush()
    stale = Backtest(
        strategy_version_id=version.id,
        start_date=datetime(2018, 1, 1).date(),
        end_date=datetime(2018, 2, 1).date(),
        status=BacktestStatus.RUNNING,
        started_at=datetime.now(timezone.utc) - timedelta(hours=2),
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    fresh = Backtest(
        strategy_version_id=version.id,
        start_date=datetime(2018, 1, 1).date(),
        end_date=datetime(2018, 2, 1).date(),
        status=BacktestStatus.QUEUED,
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([stale, fresh])
    db.commit()
    stale_id, fresh_id = stale.id, fresh.id
    db.close()

    from services.api.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AXIOM_LEAN_TIMEOUT_SECONDS", "60")
    get_settings.cache_clear()

    n = reconcile_orphan_backtests(worker_restart=False)
    assert n >= 1
    db = Session()
    assert db.get(Backtest, stale_id).status == BacktestStatus.FAILED
    assert db.get(Backtest, stale_id).error["code"] == "orphaned_by_restart"
    assert db.get(Backtest, fresh_id).status == BacktestStatus.QUEUED
    db.close()


def test_worker_restart_fails_inflight(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from services.api import db as db_module
    from services.api.db import Base

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr("services.worker.tasks.SessionLocal", Session)
    monkeypatch.setattr(db_module, "SessionLocal", Session)

    db = Session()
    strategy = Strategy(name="s2", status=StrategyStatus.DRAFT)
    db.add(strategy)
    db.flush()
    version = StrategyVersion(strategy_id=strategy.id, version=1, code="x", config={})
    db.add(version)
    db.flush()
    running = Backtest(
        id=uuid4(),
        strategy_version_id=version.id,
        start_date=datetime(2018, 1, 1).date(),
        end_date=datetime(2018, 2, 1).date(),
        status=BacktestStatus.STARTING,
        started_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db.add(running)
    db.commit()
    rid = running.id
    db.close()

    n = reconcile_orphan_backtests(worker_restart=True)
    assert n == 1
    db = Session()
    assert db.get(Backtest, rid).status == BacktestStatus.FAILED
    db.close()
