from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.db import Base
from services.api.models import (
    Backtest,
    BacktestEquity,
    BacktestStatus,
    Strategy,
    StrategyStatus,
    StrategyVersion,
    ValidationKind,
    ValidationRun,
    ValidationRunStatus,
)


def _ts(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def _long_equity(start: date, n: int, *, drift: float) -> list[dict]:
    points: list[dict] = []
    value = 100_000.0
    day = start
    i = 0
    while len(points) < n:
        if day.weekday() < 5:
            points.append({"ts": _ts(day), "strategy_value": value})
            noise = 0.004 * ((i % 5) - 2) / 2.0
            value *= 1.0 + drift + noise
            i += 1
        day += timedelta(days=1)
    return points


def _session(monkeypatch):
    from services.api import db as db_module

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


def _add_gate(db, *, strategy_id, version_id, backtest_id, kind: ValidationKind) -> None:
    db.add(
        ValidationRun(
            strategy_id=strategy_id,
            strategy_version_id=version_id,
            backtest_id=backtest_id,
            kind=kind,
            status=ValidationRunStatus.COMPLETED,
            progress_step="Completed",
            params={},
            result={"passed": True},
            passed=True,
            finished_at=datetime.now(timezone.utc),
        )
    )


def _seed(Session, *, n_points: int = 260, drift: float = 0.002):
    db = Session()
    strategy = Strategy(name="boot", status=StrategyStatus.BACKTESTED)
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
        end_date=date(2019, 6, 1),
        status=BacktestStatus.COMPLETED,
        universe_snapshot=[{"symbol": "SPY", "effective_from": "2018-01-01", "effective_to": None}],
    )
    db.add(backtest)
    db.flush()
    for point in _long_equity(date(2018, 1, 2), n_points, drift=drift):
        db.add(
            BacktestEquity(
                backtest_id=backtest.id,
                ts=point["ts"],
                strategy_value=point["strategy_value"],
            )
        )
    run = ValidationRun(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        backtest_id=backtest.id,
        kind=ValidationKind.BOOTSTRAP,
        status=ValidationRunStatus.QUEUED,
        progress_step="Queued",
        params={"n_boot": 200, "confidence_level": 0.95, "method": "stationary", "seed": 3},
        result={},
        passed=False,
    )
    db.add(run)
    for kind in (
        ValidationKind.WALK_FORWARD,
        ValidationKind.DSR,
        ValidationKind.PBO,
        ValidationKind.SENSITIVITY,
        ValidationKind.COST,
    ):
        _add_gate(db, strategy_id=strategy.id, version_id=version.id, backtest_id=backtest.id, kind=kind)
    db.commit()
    ids = (str(run.id), strategy.id)
    db.close()
    return ids


def test_bootstrap_positive_drift_promotes(monkeypatch):
    Session = _session(monkeypatch)
    from services.worker.tasks import execute_bootstrap

    run_id, strategy_id = _seed(Session, drift=0.003)
    result = execute_bootstrap(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is True
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run.passed is True
    assert run.result["sharpe"]["low"] > 0
    assert run.result["method"] == "stationary"
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.VALIDATED
    db.close()


def test_bootstrap_zero_drift_does_not_promote(monkeypatch):
    Session = _session(monkeypatch)
    from services.worker.tasks import execute_bootstrap

    run_id, strategy_id = _seed(Session, drift=0.0)
    result = execute_bootstrap(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is False
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run.passed is False
    assert run.result["sharpe"]["crosses_zero"] is True
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()


def test_bootstrap_short_series_fails_loud(monkeypatch):
    Session = _session(monkeypatch)
    from services.worker.tasks import execute_bootstrap

    run_id, strategy_id = _seed(Session, n_points=40, drift=0.003)
    result = execute_bootstrap(run_id)
    assert result["status"] == "FAILED"
    assert "少于" in result["error"]
    db = Session()
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()
