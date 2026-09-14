from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from services.api.models import (
    Backtest,
    BacktestEquity,
    BacktestMetrics,
    BacktestStatus,
    DataSnapshot,
    ExperimentTrial,
    Strategy,
    StrategyStatus,
    StrategyVersion,
    ValidationKind,
    ValidationRun,
    ValidationRunStatus,
)
from services.worker.tasks import reconcile_orphan_backtests


def _session(monkeypatch):
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
    return Session


def _ts(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


class _RecoveryEngine:
    """Counting fake LEAN engine honoring cancellation like the real one."""

    def __init__(self, **_kwargs) -> None:
        self.requests: list = []
        self.cancelled: list[str] = []

    def cancel_backtest(self, backtest_id: str) -> None:
        self.cancelled.append(backtest_id)

    def run_backtest(self, request, on_progress=None):
        from quant.engine.base import BacktestEngineResult
        from quant.engine.errors import BacktestCancelled

        self.requests.append(request)
        if on_progress:
            on_progress("Running algorithm")
        if request.cancel_check is not None and request.cancel_check():
            raise BacktestCancelled("cancelled by operator")
        lookback = int((request.parameters or {}).get("lookback") or 200)
        drift = 0.0012 - (lookback - 100) * 0.000004
        points, value, day, i = [], 100_000.0, request.start_date, 0
        while len(points) < 81:
            if day.weekday() < 5:
                points.append(
                    {
                        "ts": _ts(day),
                        "strategy_value": value,
                        "benchmark_value": value,
                        "drawdown": 0.0,
                    }
                )
                value *= 1.0 + drift + (0.004 if i % 2 == 0 else -0.003)
                i += 1
            day += timedelta(days=1)
        return BacktestEngineResult(
            engine_version="quantconnect/lean:16355",
            data_version="abc",
            statistics={"sharpe": 0.4, "trade_count": 1},
            equity=points,
            trades=[],
            monthly_returns=[],
        )


def _seed_backtest(Session, *, status=BacktestStatus.QUEUED):
    from services.api import db as db_module  # noqa: F401  (kept for symmetry)

    db = Session()
    snapshot = DataSnapshot(
        id=uuid4(), snapshot_key="recovery", provider="fixture", content_sha256="b" * 64
    )
    db.add(snapshot)
    db.flush()
    strategy = Strategy(name="recovery", status=StrategyStatus.BACKTESTED)
    db.add(strategy)
    db.flush()
    strategy.family_id = strategy.id
    version = StrategyVersion(strategy_id=strategy.id, version=1, code="print(1)", config={})
    db.add(version)
    db.flush()
    backtest = Backtest(
        id=uuid4(),
        strategy_version_id=version.id,
        start_date=date(2018, 1, 1),
        end_date=date(2018, 6, 1),
        status=status,
        universe_snapshot=[{"symbol": "SPY", "effective_from": "2018-01-01", "effective_to": None}],
        data_snapshot_id=snapshot.id,
        started_at=datetime.now(timezone.utc)
        if status in (BacktestStatus.RUNNING, BacktestStatus.STARTING)
        else None,
    )
    db.add(backtest)
    db.flush()
    ids = (strategy.id, version.id, backtest.id, snapshot.id)
    db.commit()
    db.close()
    return ids


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
    monkeypatch.setenv("STREET_LEAN_TIMEOUT_SECONDS", "60")
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


def test_completed_redelivery_is_noop(monkeypatch):
    """At-least-once redelivery of finished work must not re-run the engine
    or duplicate equity, metrics, trials, or gates."""
    Session = _session(monkeypatch)
    fake = _RecoveryEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_backtest

    _sid, _vid, bid, _snap = _seed_backtest(Session)
    assert execute_backtest(str(bid))["status"] == "COMPLETED"
    assert len(fake.requests) == 1
    db = Session()
    equity_n = db.query(BacktestEquity).filter(BacktestEquity.backtest_id == bid).count()
    metrics_n = db.query(BacktestMetrics).filter(BacktestMetrics.backtest_id == bid).count()
    trials_n = db.query(ExperimentTrial).filter(ExperimentTrial.backtest_id == bid).count()
    dsr_n = (
        db.query(ValidationRun)
        .filter(ValidationRun.backtest_id == bid, ValidationRun.kind == ValidationKind.DSR)
        .count()
    )
    assert (equity_n, metrics_n, trials_n, dsr_n) == (equity_n, 1, trials_n, dsr_n)
    assert equity_n > 0
    db.close()

    again = execute_backtest(str(bid))
    assert again == {"status": "COMPLETED"}
    assert len(fake.requests) == 1
    db = Session()
    assert db.query(BacktestEquity).filter(BacktestEquity.backtest_id == bid).count() == equity_n
    assert (
        db.query(ValidationRun)
        .filter(ValidationRun.backtest_id == bid, ValidationRun.kind == ValidationKind.DSR)
        .count()
        == dsr_n
    )
    db.close()


def test_concurrent_duplicate_pickup_is_deduplicated(monkeypatch):
    Session = _session(monkeypatch)
    fake = _RecoveryEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_backtest

    _sid, _vid, bid, _snap = _seed_backtest(Session, status=BacktestStatus.RUNNING)
    result = execute_backtest(str(bid))
    assert result["status"] == BacktestStatus.RUNNING.value
    assert result["deduplicated"] is True
    assert fake.requests == []
    db = Session()
    assert db.get(Backtest, bid).status == BacktestStatus.RUNNING
    db.close()


def test_cancel_before_start_terminates_without_side_effects(monkeypatch):
    Session = _session(monkeypatch)
    fake = _RecoveryEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    monkeypatch.setattr("services.worker.tasks.backtests.is_cancel_flagged", lambda _bid: True)
    from services.worker.tasks import execute_backtest

    _sid, _vid, bid, _snap = _seed_backtest(Session)
    result = execute_backtest(str(bid))
    assert result == {"status": "CANCELLED"}
    assert fake.cancelled == [str(bid)]
    db = Session()
    row = db.get(Backtest, bid)
    assert row.status == BacktestStatus.CANCELLED
    assert db.get(BacktestMetrics, bid) is None
    assert db.query(BacktestEquity).filter(BacktestEquity.backtest_id == bid).count() == 0
    # A cancelled row stays terminal on redelivery.
    assert execute_backtest(str(bid)) == {"status": "CANCELLED"}
    assert len(fake.requests) == 1
    db.close()


def _seed_pbo(Session):
    db = Session()
    snapshot = DataSnapshot(
        id=uuid4(), snapshot_key="recovery-pbo", provider="fixture", content_sha256="c" * 64
    )
    db.add(snapshot)
    db.flush()
    strategy = Strategy(name="recovery-pbo", status=StrategyStatus.BACKTESTED)
    db.add(strategy)
    db.flush()
    strategy.family_id = strategy.id
    version = StrategyVersion(
        strategy_id=strategy.id,
        version=1,
        code='self.GetParameter("lookback")',
        config={},
    )
    db.add(version)
    db.flush()
    backtest = Backtest(
        id=uuid4(),
        strategy_version_id=version.id,
        start_date=date(2018, 1, 1),
        end_date=date(2018, 6, 1),
        status=BacktestStatus.COMPLETED,
        universe_snapshot=[{"symbol": "SPY", "effective_from": "2018-01-01", "effective_to": None}],
        data_snapshot_id=snapshot.id,
    )
    db.add(backtest)
    db.flush()
    run = ValidationRun(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        backtest_id=backtest.id,
        kind=ValidationKind.PBO,
        status=ValidationRunStatus.QUEUED,
        progress_step="Queued",
        params={
            "parameter_key": "lookback",
            "values": [100, 200],
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
            "benchmark": "SPY",
            "initial_capital": 100_000.0,
            "data_snapshot_id": str(snapshot.id),
            "universe_snapshot": backtest.universe_snapshot,
            "base_parameters": {},
        },
        result={},
        passed=False,
    )
    db.add(run)
    db.commit()
    ids = (str(run.id), strategy.id)
    db.close()
    return ids


def test_validation_completed_redelivery_is_noop(monkeypatch):
    Session = _session(monkeypatch)
    fake = _RecoveryEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from uuid import UUID

    from services.worker.tasks import execute_pbo_scan

    run_id, _sid = _seed_pbo(Session)
    first = execute_pbo_scan(run_id)
    assert first["status"] == "COMPLETED"
    requests_n = len(fake.requests)
    assert requests_n == 2
    db = Session()
    trials_n = db.query(ExperimentTrial).count()
    backtests_n = db.query(Backtest).count()
    db.close()

    again = execute_pbo_scan(run_id)
    assert again["status"] == "COMPLETED"
    assert again["run_id"] == run_id
    assert len(fake.requests) == requests_n
    db = Session()
    assert db.query(ExperimentTrial).count() == trials_n
    assert db.query(Backtest).count() == backtests_n
    assert db.get(ValidationRun, UUID(run_id)).status == ValidationRunStatus.COMPLETED
    db.close()


def test_validation_concurrent_pickup_is_deduplicated(monkeypatch):
    Session = _session(monkeypatch)
    fake = _RecoveryEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from uuid import UUID

    from services.worker.tasks import execute_pbo_scan

    run_id, _sid = _seed_pbo(Session)
    db = Session()
    run = db.get(ValidationRun, UUID(run_id))
    assert run is not None
    run.status = ValidationRunStatus.RUNNING
    db.commit()
    db.close()

    result = execute_pbo_scan(run_id)
    assert result["status"] == ValidationRunStatus.RUNNING.value
    assert result["deduplicated"] is True
    assert fake.requests == []


def test_scan_cancel_ends_in_terminal_failed_with_cancel_code(monkeypatch):
    Session = _session(monkeypatch)
    fake = _RecoveryEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    monkeypatch.setattr("services.worker.tasks.backtests.is_cancel_flagged", lambda _bid: True)
    from uuid import UUID

    from services.worker.tasks import execute_pbo_scan

    run_id, strategy_id = _seed_pbo(Session)
    result = execute_pbo_scan(run_id)
    assert result["status"] == "FAILED"
    db = Session()
    run = db.get(ValidationRun, UUID(run_id))
    assert run is not None
    assert run.status == ValidationRunStatus.FAILED
    assert run.error is not None
    assert run.error["code"] == "cancelled"
    assert db.get(Strategy, strategy_id).status == StrategyStatus.BACKTESTED
    db.close()


def test_default_reconcile_spares_fresh_running_rows(monkeypatch):
    """The boot/beat reconciler must not reap healthy in-flight work; only
    genuinely aged-out rows fail without the explicit restart flag."""
    Session = _session(monkeypatch)
    db = Session()
    strategy = Strategy(name="s3", status=StrategyStatus.DRAFT)
    db.add(strategy)
    db.flush()
    version = StrategyVersion(strategy_id=strategy.id, version=1, code="x", config={})
    db.add(version)
    db.flush()
    live_bt = Backtest(
        strategy_version_id=version.id,
        start_date=date(2018, 1, 1),
        end_date=date(2018, 2, 1),
        status=BacktestStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    live_run = ValidationRun(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        kind=ValidationKind.PBO,
        status=ValidationRunStatus.RUNNING,
        progress_step="Config 1/2",
        params={"values": [100, 200]},
        result={},
        passed=False,
    )
    db.add_all([live_bt, live_run])
    db.commit()
    bt_id, run_id = live_bt.id, live_run.id
    db.close()

    assert reconcile_orphan_backtests() == 0
    db = Session()
    assert db.get(Backtest, bt_id).status == BacktestStatus.RUNNING
    assert db.get(ValidationRun, run_id).status == ValidationRunStatus.RUNNING
    db.close()
