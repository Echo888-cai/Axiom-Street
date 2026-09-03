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


def _weekdays(start: date, end: date) -> list[date]:
    days: list[date] = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def _two_year_market(*, strategy: str) -> list[dict]:
    days = _weekdays(date(2018, 1, 2), date(2019, 12, 31))
    crash_start = next(day for day in days if day >= date(2018, 7, 1))
    bench = 100_000.0
    strat = 100_000.0
    points = [{"ts": _ts(days[0]), "strategy_value": strat, "benchmark_value": bench}]
    for i, day in enumerate(days[1:]):
        if day == crash_start:
            bench_ret = -0.21
        elif date(2018, 7, 1) <= day <= date(2018, 12, 31):
            bench_ret = -0.008 + 0.006 * ((i % 5) - 2) / 2.0
        elif day.year == 2019 and day.month <= 6:
            bench_ret = 0.006 + 0.001 * ((i % 5) - 2) / 2.0
        else:
            bench_ret = 0.0015 + 0.0008 * ((i % 5) - 2) / 2.0
        bench *= 1.0 + bench_ret
        if strategy == "hold":
            strat *= 1.0 + bench_ret
        else:
            strat *= 1.0 + 0.001 + 0.0006 * ((i % 7) - 3) / 3.0
        points.append({"ts": _ts(day), "strategy_value": strat, "benchmark_value": bench})
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


def _seed(Session, *, strategy: str = "robust"):
    db = Session()
    row = Strategy(name="regime", status=StrategyStatus.BACKTESTED)
    db.add(row)
    db.flush()
    row.family_id = row.id
    version = StrategyVersion(strategy_id=row.id, version=1, code="print(1)", config={})
    db.add(version)
    db.flush()
    backtest = Backtest(
        id=uuid4(),
        strategy_version_id=version.id,
        start_date=date(2018, 1, 1),
        end_date=date(2019, 12, 31),
        status=BacktestStatus.COMPLETED,
        universe_snapshot=[{"symbol": "SPY", "effective_from": "2018-01-01", "effective_to": None}],
    )
    db.add(backtest)
    db.flush()
    for point in _two_year_market(strategy=strategy):
        db.add(
            BacktestEquity(
                backtest_id=backtest.id,
                ts=point["ts"],
                strategy_value=point["strategy_value"],
                benchmark_value=point["benchmark_value"],
            )
        )
    run = ValidationRun(
        strategy_id=row.id,
        strategy_version_id=version.id,
        backtest_id=backtest.id,
        kind=ValidationKind.REGIME,
        status=ValidationRunStatus.QUEUED,
        progress_step="Queued",
        params={},
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
        ValidationKind.BOOTSTRAP,
        ValidationKind.SPA,
    ):
        _add_gate(db, strategy_id=row.id, version_id=version.id, backtest_id=backtest.id, kind=kind)
    db.commit()
    ids = (str(run.id), row.id)
    db.close()
    return ids


def test_regime_robust_promotes(monkeypatch):
    Session = _session(monkeypatch)
    from services.worker.tasks import execute_regime

    run_id, strategy_id = _seed(Session, strategy="robust")
    result = execute_regime(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is True
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run.passed is True
    assert run.result["single_regime"] is False
    keys = {item["key"] for item in run.result["slices"]}
    assert {"bull", "bear", "high_vol", "low_vol", "hike", "cut", "covid_2020_03"} <= keys
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.VALIDATED
    db.close()


def test_regime_buy_and_hold_does_not_promote(monkeypatch):
    Session = _session(monkeypatch)
    from services.worker.tasks import execute_regime

    run_id, strategy_id = _seed(Session, strategy="hold")
    result = execute_regime(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is False
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run.passed is False
    assert "熊市" in run.result["reason"]
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()


def test_regime_missing_benchmark_fails_loud(monkeypatch):
    Session = _session(monkeypatch)
    from services.worker.tasks import execute_regime

    run_id, strategy_id = _seed(Session, strategy="robust")
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    db.query(BacktestEquity).filter(BacktestEquity.backtest_id == run.backtest_id).update(
        {"benchmark_value": None}
    )
    db.commit()
    db.close()
    result = execute_regime(run_id)
    assert result["status"] == "FAILED"
    assert "基准净值" in result["error"]
    db = Session()
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()
