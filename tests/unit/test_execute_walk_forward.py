from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from quant.engine.base import BacktestEngineResult
from quant.validation.walk_forward import WalkForwardSpec, build_folds
from services.api.db import Base
from services.api.models import (
    Backtest,
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


def _ts(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def _equity(start: date, end: date, *, ret_fn) -> list[dict]:
    points: list[dict] = []
    value = 100_000.0
    day = start
    i = 0
    while day <= end:
        if day.weekday() < 5:
            points.append(
                {
                    "ts": _ts(day),
                    "strategy_value": value,
                    "benchmark_value": value,
                    "drawdown": 0.0,
                }
            )
            value *= 1.0 + ret_fn(day, i)
            i += 1
        day += timedelta(days=1)
    return points


class _WfEngine:
    def __init__(self, **_kwargs) -> None:
        self.pattern = "consistent"
        self.requests: list = []

    def cancel_backtest(self, _backtest_id: str) -> None:
        return None

    def run_backtest(self, request, on_progress=None) -> BacktestEngineResult:
        self.requests.append(request)
        if on_progress:
            on_progress("Running algorithm")
        oos_year_start = date(request.end_date.year, 1, 1)

        def ret_fn(day: date, i: int) -> float:
            shock = 0.004 if i % 2 == 0 else -0.003
            if self.pattern == "overfit":
                drift = -0.002 if day >= oos_year_start else 0.003
            else:
                drift = 0.0004
            return drift + shock

        equity = _equity(request.start_date, request.end_date, ret_fn=ret_fn)
        return BacktestEngineResult(
            engine_version="quantconnect/lean:16355",
            data_version="abc",
            statistics={"sharpe": 0.2, "extras": {}},
            equity=equity,
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


def _add_scan_gate(db, *, strategy, version, backtest, kind, passed: bool) -> None:
    """P1.3b: stubbed scan gates carry scope-checked sub-backtest evidence."""
    bench = backtest.benchmark or "SPY"
    cap = float(backtest.initial_capital or 100_000.0)
    uni = backtest.universe_snapshot or []
    base_params = dict(backtest.parameters or {})

    def _sub(params):
        row = Backtest(
            id=uuid4(),
            strategy_version_id=version.id,
            start_date=backtest.start_date,
            end_date=backtest.end_date,
            benchmark=bench,
            initial_capital=cap,
            status=BacktestStatus.COMPLETED,
            parameters=params,
            data_snapshot_id=backtest.data_snapshot_id,
            universe_snapshot=uni,
            engine_version=backtest.engine_version,
            data_version=backtest.data_version,
        )
        db.add(row)
        db.flush()
        return row

    params: dict = {}
    result: dict = {"passed": passed}
    if kind == ValidationKind.PBO:
        subs = [_sub({**base_params, "lookback": v}) for v in (100, 200)]
        params = {
            "parameter_key": "lookback",
            "values": [100, 200],
            "start_date": backtest.start_date.isoformat(),
            "end_date": backtest.end_date.isoformat(),
        }
        result = {"backtest_ids": [str(r.id) for r in subs], "pbo": 0.2, "passed": passed}
    elif kind == ValidationKind.SENSITIVITY:
        subs = [_sub({**base_params, "lookback": v}) for v in (100, 150, 200)]
        params = {
            "parameter_key": "lookback",
            "values": [100, 150, 200],
            "start_date": backtest.start_date.isoformat(),
            "end_date": backtest.end_date.isoformat(),
        }
        result = {"backtest_ids": [str(r.id) for r in subs], "passed": passed}
    elif kind == ValidationKind.COST:
        subs = [_sub({**base_params, "slippage_bps": c, "fee_usd": 0.0}) for c in (0.0, 5.0, 10.0)]
        params = {
            "costs_bps": [0.0, 5.0, 10.0],
            "start_date": backtest.start_date.isoformat(),
            "end_date": backtest.end_date.isoformat(),
        }
        result = {"backtest_ids": [str(r.id) for r in subs], "passed": passed}
    elif kind == ValidationKind.SPA:
        subs = [_sub({**base_params}) for _ in range(2)]
        for i, sub in enumerate(subs):
            db.add(
                ExperimentTrial(
                    backtest_id=sub.id,
                    data_snapshot_id=backtest.data_snapshot_id,
                    strategy_id=strategy.id,
                    strategy_family=strategy.family_id or strategy.id,
                    parameters=dict(sub.parameters or {}),
                    parameter_hash=f"stub-spa-{sub.id}",
                    observed_sharpe=0.2 + 0.1 * i,
                )
            )
        db.flush()
        model_ids = sorted(str(r.id) for r in subs)
        params = {
            "family_id": str(strategy.family_id or strategy.id),
            "data_snapshot_id": str(backtest.data_snapshot_id)
            if backtest.data_snapshot_id
            else None,
            "n_models": 2,
            "trial_candidate_ids": model_ids,
        }
        result = {"models": [{"backtest_id": mid} for mid in model_ids], "passed": passed}
    db.add(
        ValidationRun(
            strategy_id=strategy.id,
            strategy_version_id=version.id,
            backtest_id=backtest.id,
            kind=kind,
            status=ValidationRunStatus.COMPLETED,
            progress_step="Completed",
            params=params,
            result=result,
            passed=passed,
            finished_at=datetime.now(timezone.utc),
        )
    )


def _seed(
    Session,
    *,
    dsr_passed: bool = True,
    pbo_passed: bool | None = True,
    sensitivity_passed: bool | None = True,
    cost_passed: bool | None = True,
    bootstrap_passed: bool | None = True,
    regime_passed: bool | None = True,
    spa_passed: bool | None = True,
    strategy_status: StrategyStatus = StrategyStatus.BACKTESTED,
):
    db = Session()
    snapshot = DataSnapshot(
        id=uuid4(), snapshot_key="evidence", provider="fixture", content_sha256="a" * 64
    )
    db.add(snapshot)
    db.flush()
    strategy = Strategy(name="wf", status=strategy_status)
    db.add(strategy)
    db.flush()
    strategy.family_id = strategy.id
    version = StrategyVersion(strategy_id=strategy.id, version=1, code="print(1)", config={})
    db.add(version)
    db.flush()
    backtest = Backtest(
        data_snapshot_id=snapshot.id,
        id=uuid4(),
        strategy_version_id=version.id,
        start_date=date(2018, 1, 1),
        end_date=date(2020, 12, 31),
        status=BacktestStatus.COMPLETED,
        universe_snapshot=[{"symbol": "SPY", "effective_from": "2018-01-01", "effective_to": None}],
    )
    db.add(backtest)
    db.flush()
    folds = build_folds(
        WalkForwardSpec(
            start=date(2018, 1, 1),
            end=date(2020, 12, 31),
            train_years=1,
            test_years=1,
            mode="rolling",
        )
    )
    run = ValidationRun(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        backtest_id=backtest.id,
        kind=ValidationKind.WALK_FORWARD,
        status=ValidationRunStatus.QUEUED,
        progress_step="Queued",
        params={
            "mode": "rolling",
            "train_years": 1,
            "test_years": 1,
            "embargo_days": 1,
            "start_date": "2018-01-01",
            "end_date": "2020-12-31",
            "benchmark": "SPY",
            "initial_capital": 100_000.0,
            "data_snapshot_id": str(snapshot.id),
            "universe_snapshot": backtest.universe_snapshot,
            "parameters": {},
            "folds": [fold.to_dict() for fold in folds],
        },
        result={},
        passed=False,
    )
    db.add(run)
    db.add(
        ValidationRun(
            strategy_id=strategy.id,
            strategy_version_id=version.id,
            backtest_id=backtest.id,
            kind=ValidationKind.DSR,
            status=ValidationRunStatus.COMPLETED,
            progress_step="Completed",
            params={},
            result={"dsr": 0.99, "passed": dsr_passed},
            passed=dsr_passed,
            finished_at=datetime.now(timezone.utc),
        )
    )
    if pbo_passed is not None:
        _add_scan_gate(
            db,
            strategy=strategy,
            version=version,
            backtest=backtest,
            kind=ValidationKind.PBO,
            passed=pbo_passed,
        )
    if sensitivity_passed is not None:
        _add_scan_gate(
            db,
            strategy=strategy,
            version=version,
            backtest=backtest,
            kind=ValidationKind.SENSITIVITY,
            passed=sensitivity_passed,
        )
    if cost_passed is not None:
        _add_scan_gate(
            db,
            strategy=strategy,
            version=version,
            backtest=backtest,
            kind=ValidationKind.COST,
            passed=cost_passed,
        )
    if bootstrap_passed is not None:
        db.add(
            ValidationRun(
                strategy_id=strategy.id,
                strategy_version_id=version.id,
                backtest_id=backtest.id,
                kind=ValidationKind.BOOTSTRAP,
                status=ValidationRunStatus.COMPLETED,
                progress_step="Completed",
                params={"n_boot": 400},
                result={"passed": bootstrap_passed},
                passed=bootstrap_passed,
                finished_at=datetime.now(timezone.utc),
            )
        )
    if regime_passed is not None:
        db.add(
            ValidationRun(
                strategy_id=strategy.id,
                strategy_version_id=version.id,
                backtest_id=backtest.id,
                kind=ValidationKind.REGIME,
                status=ValidationRunStatus.COMPLETED,
                progress_step="Completed",
                params={},
                result={"passed": regime_passed},
                passed=regime_passed,
                finished_at=datetime.now(timezone.utc),
            )
        )
    if spa_passed is not None:
        _add_scan_gate(
            db,
            strategy=strategy,
            version=version,
            backtest=backtest,
            kind=ValidationKind.SPA,
            passed=spa_passed,
        )
    db.commit()
    ids = (str(run.id), strategy.id)
    db.close()
    return ids


def test_walk_forward_consistent_promotes_when_dsr_passed(monkeypatch):
    Session = _session(monkeypatch)
    fake = _WfEngine()
    fake.pattern = "consistent"
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_walk_forward

    run_id, strategy_id = _seed(Session, dsr_passed=True)
    result = execute_walk_forward(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is True
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run.status == ValidationRunStatus.COMPLETED
    assert run.passed is True
    assert run.result["overfit_collapse"] is False
    assert len(fake.requests) == 2
    assert fake.requests[0].end_date == date(2019, 12, 31)
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.VALIDATED
    db.close()


def test_walk_forward_collapse_does_not_promote(monkeypatch):
    Session = _session(monkeypatch)
    fake = _WfEngine()
    fake.pattern = "overfit"
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_walk_forward

    run_id, strategy_id = _seed(Session, dsr_passed=True)
    result = execute_walk_forward(run_id)
    assert result["passed"] is False
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run.result["overfit_collapse"] is True
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()


def test_walk_forward_without_dsr_pass_stays_backtested(monkeypatch):
    Session = _session(monkeypatch)
    fake = _WfEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_walk_forward

    run_id, strategy_id = _seed(Session, dsr_passed=False)
    execute_walk_forward(run_id)
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run.passed is True
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()


def test_walk_forward_without_pbo_stays_backtested(monkeypatch):
    Session = _session(monkeypatch)
    fake = _WfEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_walk_forward

    run_id, strategy_id = _seed(Session, dsr_passed=True, pbo_passed=None)
    execute_walk_forward(run_id)
    db = Session()
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()


def test_walk_forward_without_sensitivity_stays_backtested(monkeypatch):
    Session = _session(monkeypatch)
    fake = _WfEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_walk_forward

    run_id, strategy_id = _seed(Session, dsr_passed=True, sensitivity_passed=None)
    execute_walk_forward(run_id)
    db = Session()
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()


def test_walk_forward_without_bootstrap_stays_backtested(monkeypatch):
    Session = _session(monkeypatch)
    fake = _WfEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_walk_forward

    run_id, strategy_id = _seed(Session, dsr_passed=True, bootstrap_passed=None)
    execute_walk_forward(run_id)
    db = Session()
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()


def test_walk_forward_without_regime_stays_backtested(monkeypatch):
    Session = _session(monkeypatch)
    fake = _WfEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_walk_forward

    run_id, strategy_id = _seed(Session, dsr_passed=True, regime_passed=None)
    execute_walk_forward(run_id)
    db = Session()
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()


def test_walk_forward_without_spa_stays_backtested(monkeypatch):
    Session = _session(monkeypatch)
    fake = _WfEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_walk_forward

    run_id, strategy_id = _seed(Session, dsr_passed=True, spa_passed=None)
    execute_walk_forward(run_id)
    db = Session()
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()


def test_failed_walk_forward_demotes_validated(monkeypatch):
    Session = _session(monkeypatch)
    fake = _WfEngine()
    fake.pattern = "overfit"
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_walk_forward

    run_id, strategy_id = _seed(Session, dsr_passed=True, strategy_status=StrategyStatus.VALIDATED)
    execute_walk_forward(run_id)
    db = Session()
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()
