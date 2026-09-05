from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from quant.engine.base import BacktestEngineResult
from services.api.db import Base
from services.api.models import (
    Backtest,
    BacktestStatus,
    ExperimentTrial,
    Strategy,
    StrategyStatus,
    StrategyVersion,
    ValidationKind,
    ValidationRun,
    ValidationRunStatus,
)


def _ts(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def _equity(start: date, n: int, *, ret: float) -> list[dict]:
    points: list[dict] = []
    value = 100_000.0
    day = start
    while len(points) < n:
        if day.weekday() < 5:
            points.append(
                {
                    "ts": _ts(day),
                    "strategy_value": value,
                    "benchmark_value": value * 0.999,
                    "drawdown": 0.0,
                }
            )
            value *= 1.0 + ret
        day += timedelta(days=1)
    return points


class _CostEngine:
    def __init__(self, **_kwargs) -> None:
        self.pattern = "survive"
        self.requests: list = []

    def cancel_backtest(self, _backtest_id: str) -> None:
        return None

    def run_backtest(self, request, on_progress=None) -> BacktestEngineResult:
        self.requests.append(request)
        if on_progress:
            on_progress("Running algorithm")
        bps = float((request.parameters or {}).get("slippage_bps") or 0)
        if self.pattern == "identical":
            alpha = 0.02
            final = 110_000.0
            trades = 8
            ret = 0.0004
        elif self.pattern == "dead":
            # 0: 0.02, 5: 0.0, 10: -0.02 → breakeven 5 bps
            alpha = 0.02 - bps * 0.004
            final = 110_000.0 - bps
            trades = 8
            ret = 0.001 - bps * 1e-5
        else:
            # 0: 0.04, 5: 0.03, 10: 0.02, 20: -0.02 → breakeven 15
            alpha = 0.04 - bps * 0.002 if bps <= 10 else 0.02 - (bps - 10) * 0.004
            final = 110_000.0 - bps
            trades = 8
            ret = 0.0012 - bps * 1e-5
        return BacktestEngineResult(
            engine_version="quantconnect/lean:16355",
            data_version="abc",
            statistics={
                "sharpe": 0.8,
                "alpha_capm": alpha,
                "final_equity": final,
                "trade_count": trades,
                "extras": {},
                "skewness": 0.0,
                "kurtosis": 0.0,
            },
            equity=_equity(request.start_date, 40, ret=ret),
            trades=[],
            monthly_returns=[],
        )


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


def _seed(Session, *, costs: list[float] | None = None):
    costs = costs or [0.0, 5.0, 10.0, 20.0]
    db = Session()
    strategy = Strategy(name="cost", status=StrategyStatus.BACKTESTED)
    db.add(strategy)
    db.flush()
    strategy.family_id = strategy.id
    version = StrategyVersion(
        strategy_id=strategy.id,
        version=1,
        code='self.GetParameter("slippage_bps")',
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
    )
    db.add(backtest)
    db.flush()
    run = ValidationRun(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        backtest_id=backtest.id,
        kind=ValidationKind.COST,
        status=ValidationRunStatus.QUEUED,
        progress_step="Queued",
        params={
            "costs_bps": costs,
            "realistic_one_way_bps": 5.0,
            "start_date": "2018-01-01",
            "end_date": "2018-06-01",
            "benchmark": "SPY",
            "initial_capital": 100_000.0,
            "universe_snapshot": backtest.universe_snapshot,
            "base_parameters": {},
        },
        result={},
        passed=False,
    )
    db.add(run)
    for kind in (
        ValidationKind.WALK_FORWARD,
        ValidationKind.DSR,
        ValidationKind.PBO,
        ValidationKind.SENSITIVITY,
        ValidationKind.BOOTSTRAP,
        ValidationKind.REGIME,
        ValidationKind.SPA,
    ):
        _add_gate(
            db, strategy_id=strategy.id, version_id=version.id, backtest_id=backtest.id, kind=kind
        )
    db.commit()
    ids = (str(run.id), strategy.id)
    db.close()
    return ids


def test_cost_above_realistic_promotes(monkeypatch):
    Session = _session(monkeypatch)
    fake = _CostEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_cost_scan

    run_id, strategy_id = _seed(Session)
    result = execute_cost_scan(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is True
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run is not None
    assert float(run.result["breakeven_bps"]) == 15.0
    assert "15.00 bps" in str(run.result["conclusion"])
    assert fake.requests[0].parameters["slippage_bps"] == 0.0
    assert fake.requests[0].parameters["fee_usd"] == 0.0
    n_trials = db.scalar(select(func.count()).select_from(ExperimentTrial))
    assert n_trials == 4
    strategy = db.get(Strategy, strategy_id)
    assert strategy is not None
    assert strategy.status == StrategyStatus.VALIDATED
    db.close()


def test_cost_at_realistic_does_not_promote(monkeypatch):
    Session = _session(monkeypatch)
    fake = _CostEngine()
    fake.pattern = "dead"
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_cost_scan

    run_id, strategy_id = _seed(Session)
    result = execute_cost_scan(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is False
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run is not None
    assert float(run.result["breakeven_bps"]) == 5.0
    assert "判死" in str(run.result["reason"])
    strategy = db.get(Strategy, strategy_id)
    assert strategy is not None
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()


def test_identical_cost_nav_fails_loud(monkeypatch):
    Session = _session(monkeypatch)
    fake = _CostEngine()
    fake.pattern = "identical"
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_cost_scan

    run_id, _strategy_id = _seed(Session)
    result = execute_cost_scan(run_id)
    assert result["status"] == "FAILED"
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run is not None
    assert run.error is not None
    assert "slippage_bps" in str(run.error.get("message"))
    db.close()
