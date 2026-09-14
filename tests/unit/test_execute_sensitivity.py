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


def _equity(start: date, n: int, *, ret: float) -> list[dict]:
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
            value *= 1.0 + ret
            i += 1
        day += timedelta(days=1)
    return points


class _SensEngine:
    def __init__(self, **_kwargs) -> None:
        self.pattern = "plateau"
        self.requests: list = []

    def cancel_backtest(self, _backtest_id: str) -> None:
        return None

    def run_backtest(self, request, on_progress=None) -> BacktestEngineResult:
        self.requests.append(request)
        if on_progress:
            on_progress("Running algorithm")
        lookback = int((request.parameters or {}).get("lookback") or 200)
        if self.pattern == "identical":
            sharpe = 1.2
            final = 110_000.0
            ret = 0.0004
        elif self.pattern == "knife":
            sharpe = 2.0 if lookback == 200 else 0.2
            final = 110_000.0 + lookback
            ret = 0.002 if lookback == 200 else 0.0002
        else:
            sharpe = 1.40 - abs(lookback - 200) * 0.001
            final = 110_000.0 + lookback
            ret = 0.0012 - abs(lookback - 200) * 1e-6
        return BacktestEngineResult(
            engine_version="quantconnect/lean:16355",
            data_version="abc",
            statistics={
                "sharpe": sharpe,
                "final_equity": final,
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
    # P1.3b: stubbed gates carry real execution evidence so promotion reflects
    # scope-checked scans, not empty {"passed": True} placeholders.
    anchor = db.get(Backtest, backtest_id)
    assert anchor is not None
    snap = anchor.data_snapshot_id
    uni = anchor.universe_snapshot or []
    bench = anchor.benchmark or "SPY"
    cap = float(anchor.initial_capital or 100_000.0)
    base_params = dict(anchor.parameters or {})

    def _sub(params):
        row = Backtest(
            id=uuid4(),
            strategy_version_id=version_id,
            start_date=anchor.start_date,
            end_date=anchor.end_date,
            benchmark=bench,
            initial_capital=cap,
            status=BacktestStatus.COMPLETED,
            parameters=params,
            data_snapshot_id=snap,
            universe_snapshot=uni,
            engine_version=anchor.engine_version,
            data_version=anchor.data_version,
        )
        db.add(row)
        db.flush()
        return row

    params: dict = {}
    result: dict = {"passed": True}
    if kind == ValidationKind.PBO:
        subs = [_sub({**base_params, "lookback": v}) for v in (100, 200)]
        params = {
            "parameter_key": "lookback",
            "values": [100, 200],
            "start_date": anchor.start_date.isoformat(),
            "end_date": anchor.end_date.isoformat(),
        }
        result = {"backtest_ids": [str(r.id) for r in subs], "pbo": 0.2, "passed": True}
    elif kind == ValidationKind.SENSITIVITY:
        subs = [_sub({**base_params, "lookback": v}) for v in (100, 150, 200)]
        params = {
            "parameter_key": "lookback",
            "values": [100, 150, 200],
            "start_date": anchor.start_date.isoformat(),
            "end_date": anchor.end_date.isoformat(),
        }
        result = {"backtest_ids": [str(r.id) for r in subs], "passed": True}
    elif kind == ValidationKind.COST:
        subs = [_sub({**base_params, "slippage_bps": c, "fee_usd": 0.0}) for c in (0.0, 5.0, 10.0)]
        params = {
            "costs_bps": [0.0, 5.0, 10.0],
            "start_date": anchor.start_date.isoformat(),
            "end_date": anchor.end_date.isoformat(),
        }
        result = {"backtest_ids": [str(r.id) for r in subs], "passed": True}
    elif kind == ValidationKind.WALK_FORWARD:
        folds = [
            {
                "index": 0,
                "is_start": anchor.start_date.isoformat(),
                "is_end": anchor.start_date.isoformat(),
                "oos_start": anchor.start_date.isoformat(),
                "oos_end": anchor.end_date.isoformat(),
            },
            {
                "index": 1,
                "is_start": anchor.start_date.isoformat(),
                "is_end": anchor.start_date.isoformat(),
                "oos_start": anchor.start_date.isoformat(),
                "oos_end": anchor.end_date.isoformat(),
            },
        ]
        params = {
            "start_date": anchor.start_date.isoformat(),
            "end_date": anchor.end_date.isoformat(),
            "benchmark": bench,
            "initial_capital": cap,
            "folds": folds,
        }
        result = {
            "folds": folds,
            "execution": {
                "engine_version": anchor.engine_version,
                "data_version": anchor.data_version,
                "data_snapshot_id": str(snap) if snap else None,
                "benchmark": bench,
                "initial_capital": cap,
                "universe_snapshot": uni,
                "parameters": base_params,
                "folds": folds,
            },
            "passed": True,
        }
    elif kind == ValidationKind.SPA:
        subs = [_sub({**base_params}) for _ in range(2)]
        strategy = db.get(Strategy, strategy_id)
        fam = str(strategy.family_id or strategy_id) if strategy else str(strategy_id)
        for i, sub in enumerate(subs):
            db.add(
                ExperimentTrial(
                    backtest_id=sub.id,
                    data_snapshot_id=snap,
                    strategy_id=strategy_id,
                    strategy_family=strategy.family_id if strategy else strategy_id,
                    parameters=dict(sub.parameters or {}),
                    parameter_hash=f"stub-spa-{sub.id}",
                    observed_sharpe=0.2 + 0.1 * i,
                )
            )
        db.flush()
        model_ids = sorted(str(r.id) for r in subs)
        params = {
            "family_id": fam,
            "data_snapshot_id": str(snap) if snap else None,
            "n_models": 2,
            "trial_candidate_ids": model_ids,
        }
        result = {"models": [{"backtest_id": mid} for mid in model_ids], "passed": True}
    db.add(
        ValidationRun(
            strategy_id=strategy_id,
            strategy_version_id=version_id,
            backtest_id=backtest_id,
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
    values = values or [100, 150, 200, 250, 300]
    db = Session()
    snapshot = DataSnapshot(
        id=uuid4(), snapshot_key="evidence", provider="fixture", content_sha256="a" * 64
    )
    db.add(snapshot)
    db.flush()
    strategy = Strategy(name="sens", status=StrategyStatus.BACKTESTED)
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
        kind=ValidationKind.SENSITIVITY,
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
    for kind in (
        ValidationKind.WALK_FORWARD,
        ValidationKind.DSR,
        ValidationKind.PBO,
        ValidationKind.COST,
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


def test_plateau_promotes(monkeypatch):
    Session = _session(monkeypatch)
    fake = _SensEngine()
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_sensitivity_scan

    run_id, strategy_id = _seed(Session)
    result = execute_sensitivity_scan(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is True
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run is not None
    assert run.result["shape"] == "plateau"
    assert run.result["plateau_width"] >= 3
    assert len(fake.requests) == 5
    n_trials = db.scalar(select(func.count()).select_from(ExperimentTrial))
    assert n_trials == 7  # 2 stub SPA trials + five scan configs
    strategy = db.get(Strategy, strategy_id)
    assert strategy is not None
    # The scan added family trials, so seed-time SPA conclusions are expired.
    assert strategy.status == StrategyStatus.BACKTESTED
    _refresh_family_gates(db, strategy_id=strategy_id, backtest_id=run.backtest_id)
    db.refresh(strategy)
    assert strategy.status == StrategyStatus.VALIDATED
    db.close()


def test_knife_edge_does_not_promote(monkeypatch):
    Session = _session(monkeypatch)
    fake = _SensEngine()
    fake.pattern = "knife"
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_sensitivity_scan

    run_id, strategy_id = _seed(Session)
    result = execute_sensitivity_scan(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is False
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run is not None
    assert run.result["shape"] == "knife_edge"
    strategy = db.get(Strategy, strategy_id)
    assert strategy is not None
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()


def test_identical_nav_fails_loud(monkeypatch):
    Session = _session(monkeypatch)
    fake = _SensEngine()
    fake.pattern = "identical"
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_sensitivity_scan

    run_id, strategy_id = _seed(Session)
    result = execute_sensitivity_scan(run_id)
    assert result["status"] == "FAILED"
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run is not None
    assert run.error is not None
    assert "无法区分" in str(run.error.get("message"))
    strategy = db.get(Strategy, strategy_id)
    assert strategy is not None
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()
