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


def _equity(start: date, n: int, *, ret_fn) -> list[dict]:
    points: list[dict] = []
    value = 100_000.0
    day = start
    i = 0
    while len(points) < n:
        if day.weekday() < 5:
            points.append(
                {
                    "ts": _ts(day),
                    "strategy_value": value,
                    "benchmark_value": value,
                    "drawdown": 0.0,
                }
            )
            value *= 1.0 + ret_fn(i)
            i += 1
        day += timedelta(days=1)
    return points


class _PboEngine:
    def __init__(self, **_kwargs) -> None:
        self.pattern = "consistent"
        self.requests: list = []

    def cancel_backtest(self, _backtest_id: str) -> None:
        return None

    def run_backtest(self, request, on_progress=None) -> BacktestEngineResult:
        self.requests.append(request)
        if on_progress:
            on_progress("Running algorithm")
        lookback = int((request.parameters or {}).get("lookback") or 200)

        def ret_fn(i: int) -> float:
            shock = 0.004 if i % 2 == 0 else -0.003
            if self.pattern == "identical":
                return 0.0004 + shock
            if self.pattern == "overfit":
                # Each lookback is lucky on one CSCV slice and mean-reverts on the opposite
                # slice, so the IS-best is OOS-worst (Bailey-style overfitting).
                column = {100: 0, 150: 1, 200: 2, 250: 3}.get(lookback, 0)
                extra = 0.0
                if column * 10 <= i < column * 10 + 10:
                    extra = 0.05
                opposite = ((column + 4) % 8) * 10
                if opposite <= i < opposite + 10:
                    extra = -0.05
                return 0.0003 + extra + column * 1e-5
            drift = 0.0012 - (lookback - 100) * 0.000004
            return drift + shock

        equity = _equity(request.start_date, 81, ret_fn=ret_fn)
        return BacktestEngineResult(
            engine_version="quantconnect/lean:16355",
            data_version="abc",
            statistics={"sharpe": 0.4, "extras": {}, "skewness": 0.0, "kurtosis": 0.0},
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


def _add_evidence_gate(db, *, strategy, version, backtest, kind) -> None:
    """P1.3b: stubbed gates carry scope-checked execution evidence."""
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
    result: dict = {"passed": True}
    if kind == ValidationKind.WALK_FORWARD:
        folds = [
            {
                "index": 0,
                "is_start": backtest.start_date.isoformat(),
                "is_end": backtest.start_date.isoformat(),
                "oos_start": backtest.start_date.isoformat(),
                "oos_end": backtest.end_date.isoformat(),
            },
            {
                "index": 1,
                "is_start": backtest.start_date.isoformat(),
                "is_end": backtest.start_date.isoformat(),
                "oos_start": backtest.start_date.isoformat(),
                "oos_end": backtest.end_date.isoformat(),
            },
        ]
        params = {
            "start_date": backtest.start_date.isoformat(),
            "end_date": backtest.end_date.isoformat(),
            "benchmark": bench,
            "initial_capital": cap,
            "folds": folds,
        }
        result = {
            "folds": folds,
            "execution": {
                "engine_version": backtest.engine_version,
                "data_version": backtest.data_version,
                "data_snapshot_id": str(backtest.data_snapshot_id)
                if backtest.data_snapshot_id
                else None,
                "benchmark": bench,
                "initial_capital": cap,
                "universe_snapshot": uni,
                "parameters": base_params,
                "folds": folds,
            },
            "passed": True,
        }
    elif kind == ValidationKind.SENSITIVITY:
        subs = [_sub({**base_params, "lookback": v}) for v in (100, 150, 200)]
        params = {
            "parameter_key": "lookback",
            "values": [100, 150, 200],
            "start_date": backtest.start_date.isoformat(),
            "end_date": backtest.end_date.isoformat(),
        }
        result = {"backtest_ids": [str(r.id) for r in subs], "passed": True}
    elif kind == ValidationKind.COST:
        subs = [_sub({**base_params, "slippage_bps": c, "fee_usd": 0.0}) for c in (0.0, 5.0, 10.0)]
        params = {
            "costs_bps": [0, 5, 10],
            "start_date": backtest.start_date.isoformat(),
            "end_date": backtest.end_date.isoformat(),
        }
        result = {"backtest_ids": [str(r.id) for r in subs], "passed": True}
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
        result = {"models": [{"backtest_id": mid} for mid in model_ids], "passed": True}
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
            passed=True,
            finished_at=datetime.now(timezone.utc),
        )
    )


def _seed(Session, *, values: list[int] | None = None):
    values = values or [100, 200]
    db = Session()
    snapshot = DataSnapshot(
        id=uuid4(), snapshot_key="evidence", provider="fixture", content_sha256="a" * 64
    )
    db.add(snapshot)
    db.flush()
    strategy = Strategy(name="pbo", status=StrategyStatus.BACKTESTED)
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
        data_snapshot_id=snapshot.id,
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
        kind=ValidationKind.PBO,
        status=ValidationRunStatus.QUEUED,
        progress_step="Queued",
        params={
            "parameter_key": "lookback",
            "values": values,
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
    for _kind in (
        ValidationKind.WALK_FORWARD,
        ValidationKind.SENSITIVITY,
        ValidationKind.COST,
        ValidationKind.SPA,
    ):
        _add_evidence_gate(db, strategy=strategy, version=version, backtest=backtest, kind=_kind)
    db.add(
        ValidationRun(
            strategy_id=strategy.id,
            strategy_version_id=version.id,
            backtest_id=backtest.id,
            kind=ValidationKind.DSR,
            status=ValidationRunStatus.COMPLETED,
            progress_step="Completed",
            params={},
            result={"dsr": 0.99, "passed": True},
            passed=True,
            finished_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        ValidationRun(
            strategy_id=strategy.id,
            strategy_version_id=version.id,
            backtest_id=backtest.id,
            kind=ValidationKind.BOOTSTRAP,
            status=ValidationRunStatus.COMPLETED,
            progress_step="Completed",
            params={"n_boot": 400},
            result={"passed": True},
            passed=True,
            finished_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        ValidationRun(
            strategy_id=strategy.id,
            strategy_version_id=version.id,
            backtest_id=backtest.id,
            kind=ValidationKind.REGIME,
            status=ValidationRunStatus.COMPLETED,
            progress_step="Completed",
            params={},
            result={"passed": True},
            passed=True,
            finished_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    ids = (str(run.id), strategy.id, version.id)
    db.close()
    return ids


def _refresh_family_gates(db, *, strategy_id, backtest_id) -> None:
    """Recompute family-bound DSR/SPA on the post-scan ledger (P1.3c workflow:
    searching expires seed-time conclusions; fresh ones re-validate)."""
    from services.api.services.validation import (
        dsr_trial_rows,
        dsr_trial_set_hash,
        maybe_apply_validated,
        spa_candidate_ids,
    )

    strategy = db.get(Strategy, strategy_id)
    anchor = db.get(Backtest, backtest_id)
    assert strategy is not None and anchor is not None
    family = strategy.family_id or strategy.id
    version_id = anchor.strategy_version_id
    trials = dsr_trial_rows(db, family_id=family, snapshot_id=anchor.data_snapshot_id)
    db.add(
        ValidationRun(
            strategy_id=strategy_id,
            strategy_version_id=version_id,
            backtest_id=anchor.id,
            kind=ValidationKind.DSR,
            status=ValidationRunStatus.COMPLETED,
            progress_step="Completed",
            params={
                "n_trials": max(sum(1 for t in trials if t.observed_sharpe is not None), 1),
                "family_id": str(family),
                "data_snapshot_id": str(anchor.data_snapshot_id)
                if anchor.data_snapshot_id
                else None,
                "trial_set_hash": dsr_trial_set_hash(trials),
            },
            result={"dsr": 0.99, "passed": True},
            passed=True,
            finished_at=datetime.now(timezone.utc),
        )
    )
    candidates = spa_candidate_ids(db, family_id=family, snapshot_id=anchor.data_snapshot_id)
    db.add(
        ValidationRun(
            strategy_id=strategy_id,
            strategy_version_id=version_id,
            backtest_id=anchor.id,
            kind=ValidationKind.SPA,
            status=ValidationRunStatus.COMPLETED,
            progress_step="Completed",
            params={
                "family_id": str(family),
                "data_snapshot_id": str(anchor.data_snapshot_id)
                if anchor.data_snapshot_id
                else None,
                "n_models": len(candidates),
                "trial_candidate_ids": candidates,
            },
            result={
                "models": [{"backtest_id": item} for item in candidates],
                "passed": True,
            },
            passed=True,
            finished_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    maybe_apply_validated(db, strategy_id=strategy_id, strategy_version_id=version_id)
    db.commit()


def test_pbo_scan_writes_trials_and_promotes(monkeypatch):
    Session = _session(monkeypatch)
    fake = _PboEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_pbo_scan

    run_id, strategy_id, _version_id = _seed(Session, values=[100, 200])
    result = execute_pbo_scan(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is True
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run is not None
    assert run.status == ValidationRunStatus.COMPLETED
    assert run.passed is True
    assert float(run.result["pbo"]) <= 0.5
    assert len(fake.requests) == 2
    assert fake.requests[0].parameters["lookback"] == 100
    assert fake.requests[1].parameters["lookback"] == 200
    n_trials = db.scalar(select(func.count()).select_from(ExperimentTrial))
    assert n_trials == 4  # 2 stub SPA trials + two scan configs
    n_backtests = db.scalar(select(func.count()).select_from(Backtest))
    assert n_backtests == 11  # template + two scan configs + 8 evidence stubs
    strategy = db.get(Strategy, strategy_id)
    assert strategy is not None
    # The scan added family trials, so seed-time SPA conclusions are expired.
    assert strategy.status == StrategyStatus.BACKTESTED
    _refresh_family_gates(db, strategy_id=strategy_id, backtest_id=run.backtest_id)
    db.refresh(strategy)
    assert strategy.status == StrategyStatus.VALIDATED
    db.close()


def test_identical_equity_fails_loud(monkeypatch):
    Session = _session(monkeypatch)
    fake = _PboEngine()
    fake.pattern = "identical"
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_pbo_scan

    run_id, strategy_id, _version_id = _seed(Session)
    result = execute_pbo_scan(run_id)
    assert result["status"] == "FAILED"
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run is not None
    assert run.status == ValidationRunStatus.FAILED
    assert run.error is not None
    assert "无法区分" in str(run.error.get("message"))
    strategy = db.get(Strategy, strategy_id)
    assert strategy is not None
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()


def test_overfit_scan_does_not_promote(monkeypatch):
    Session = _session(monkeypatch)
    fake = _PboEngine()
    fake.pattern = "overfit"
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_pbo_scan

    run_id, strategy_id, _version_id = _seed(Session, values=[100, 150, 200, 250])
    result = execute_pbo_scan(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is False
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run is not None
    assert float(run.result["pbo"]) > 0.5
    strategy = db.get(Strategy, strategy_id)
    assert strategy is not None
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()
