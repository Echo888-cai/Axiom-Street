from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from quant.engine.base import BacktestEngineResult
from quant.engine.errors import BacktestCancelled, EngineTimeout
from services.api.db import Base
from services.api.models import (
    Backtest,
    BacktestMetrics,
    BacktestStatus,
    ExperimentTrial,
    Strategy,
    StrategyStatus,
    StrategyVersion,
)


class _FakeEngine:
    def __init__(self, **_kwargs) -> None:
        self.risk_free_rate = 0.0
        self.fail: str | None = None
        self.last_request = None

    def cancel_backtest(self, _backtest_id: str) -> None:
        return None

    def run_backtest(self, request, on_progress=None) -> BacktestEngineResult:
        self.last_request = request
        if self.fail == "timeout":
            raise EngineTimeout("LEAN exceeded 5s")
        if self.fail == "cancel":
            raise BacktestCancelled(request.backtest_id)
        if on_progress:
            on_progress("Running algorithm")
        ts = datetime(2018, 1, 3, tzinfo=timezone.utc)
        ts2 = datetime(2018, 1, 4, tzinfo=timezone.utc)
        ts3 = datetime(2018, 1, 5, tzinfo=timezone.utc)
        return BacktestEngineResult(
            engine_version="quantconnect/lean:16355",
            data_version="abc",
            statistics={
                "sharpe": 1.25,
                "total_return": 0.1,
                "final_equity": 110_000.0,
                "trade_count": 1,
                "skewness": 0.0,
                "kurtosis": 0.0,
                "extras": {},
            },
            equity=[
                {
                    "ts": ts,
                    "strategy_value": 100_000.0,
                    "benchmark_value": 100_000.0,
                    "drawdown": 0.0,
                },
                {
                    "ts": ts2,
                    "strategy_value": 105_000.0,
                    "benchmark_value": 101_000.0,
                    "drawdown": 0.0,
                },
                {
                    "ts": ts3,
                    "strategy_value": 110_000.0,
                    "benchmark_value": 102_000.0,
                    "drawdown": 0.0,
                },
            ],
            trades=[
                {
                    "trade_date": ts,
                    "ticker": "SPY",
                    "direction": "LONG",
                    "quantity": 10,
                    "entry_price": 100.0,
                    "exit_price": 110.0,
                    "pnl": 100.0,
                    "return_pct": 0.1,
                    "holding_period": 5.0,
                    "commission": 1.0,
                    "slippage": None,
                    "signal": None,
                    "raw": {},
                }
            ],
            monthly_returns=[{"year": 2018, "month": 1, "return_pct": 0.1}],
            rolling_windows=[{"window_key": "1M", "sharpe": 1.0, "extras": {}}],
            time_series=[{"name": "turnover", "ts": ts, "value": 0.02}],
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


def _seed(Session):
    db = Session()
    strategy = Strategy(name="exec", status=StrategyStatus.DRAFT)
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
        status=BacktestStatus.QUEUED,
        progress_step="Queued",
        universe_snapshot=[{"symbol": "SPY", "effective_from": "2018-01-01", "effective_to": None}],
    )
    db.add(backtest)
    db.flush()
    db.add(
        ExperimentTrial(
            backtest_id=backtest.id,
            strategy_id=strategy.id,
            strategy_family=strategy.family_id,
            parameters={},
            parameter_hash="x",
        )
    )
    db.add(
        ExperimentTrial(
            backtest_id=None,
            strategy_id=strategy.id,
            strategy_family=strategy.family_id,
            parameters={"oos": True},
            parameter_hash="oos",
            observed_sharpe=9.99,
            is_oos=True,
        )
    )
    db.commit()
    ids = (str(backtest.id), strategy.id)
    db.close()
    return ids


def test_execute_backtest_persists_round_trips(monkeypatch):
    Session = _session(monkeypatch)
    fake = _FakeEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_backtest

    backtest_id, strategy_id = _seed(Session)
    result = execute_backtest(backtest_id)
    assert result["status"] == "COMPLETED"
    db = Session()
    bt = db.get(Backtest, __import__("uuid").UUID(backtest_id))
    assert bt.status == BacktestStatus.COMPLETED
    assert bt.engine_version == "quantconnect/lean:16355"
    metrics = db.get(BacktestMetrics, bt.id)
    assert metrics.sharpe == 1.25
    assert len(bt.trades) == 1
    assert bt.trades[0].pnl == 100.0
    assert bt.rolling_windows
    assert bt.time_series
    trial = db.query(ExperimentTrial).filter(ExperimentTrial.backtest_id == bt.id).one()
    assert trial.observed_sharpe == 1.25
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    assert metrics.deflated_sharpe is not None
    from services.api.models import ValidationKind, ValidationRun

    dsr = (
        db.query(ValidationRun)
        .filter(ValidationRun.backtest_id == bt.id, ValidationRun.kind == ValidationKind.DSR)
        .one()
    )
    assert dsr.result["n_trials"] == 1
    boot = (
        db.query(ValidationRun)
        .filter(ValidationRun.backtest_id == bt.id, ValidationRun.kind == ValidationKind.BOOTSTRAP)
        .one()
    )
    assert boot.passed is False
    assert boot.error is not None
    assert "少于" in boot.error["message"]
    db.close()


def test_execute_backtest_timeout(monkeypatch):
    Session = _session(monkeypatch)
    fake = _FakeEngine()
    fake.fail = "timeout"
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_backtest

    backtest_id, _ = _seed(Session)
    result = execute_backtest(backtest_id)
    assert result["status"] == "FAILED"
    db = Session()
    bt = db.get(Backtest, __import__("uuid").UUID(backtest_id))
    assert bt.error["code"] == "engine_timeout"
    db.close()


def test_execute_backtest_cancel(monkeypatch):
    Session = _session(monkeypatch)
    fake = _FakeEngine()
    fake.fail = "cancel"
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_backtest

    backtest_id, _ = _seed(Session)
    result = execute_backtest(backtest_id)
    assert result["status"] == "CANCELLED"
    db = Session()
    bt = db.get(Backtest, __import__("uuid").UUID(backtest_id))
    assert bt.status == BacktestStatus.CANCELLED
    db.close()


def test_execute_backtest_passes_ten_name_universe(monkeypatch):
    from quant.strategy_sdk.equal_weight import DEFAULT_EQUAL_WEIGHT_UNIVERSE

    Session = _session(monkeypatch)
    fake = _FakeEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_backtest

    backtest_id, _ = _seed(Session)
    db = Session()
    bt = db.get(Backtest, __import__("uuid").UUID(backtest_id))
    bt.universe_snapshot = [
        {"symbol": symbol, "effective_from": "2018-01-01", "effective_to": None}
        for symbol in DEFAULT_EQUAL_WEIGHT_UNIVERSE
    ]
    db.commit()
    db.close()

    result = execute_backtest(backtest_id)
    assert result["status"] == "COMPLETED"
    assert fake.last_request is not None
    assert fake.last_request.universe == list(DEFAULT_EQUAL_WEIGHT_UNIVERSE)
    assert len(fake.last_request.memberships) == 10


def test_execute_backtest_empty_universe_fails(monkeypatch):
    Session = _session(monkeypatch)
    fake = _FakeEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_backtest

    backtest_id, _ = _seed(Session)
    db = Session()
    bt = db.get(Backtest, __import__("uuid").UUID(backtest_id))
    bt.universe_snapshot = None
    db.commit()
    db.close()

    result = execute_backtest(backtest_id)
    assert result["error"] == "universe_missing"
    db = Session()
    bt = db.get(Backtest, __import__("uuid").UUID(backtest_id))
    assert bt.status == BacktestStatus.FAILED
    assert bt.error["code"] == "universe_missing"
    assert fake.last_request is None
    db.close()
