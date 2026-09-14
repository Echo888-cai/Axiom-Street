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
    return datetime(day.year, month=day.month, day=day.day, tzinfo=timezone.utc)


def _long_equity(start: date, n: int, *, drift: float, phase: int = 0) -> list[dict]:
    points: list[dict] = []
    value = 100_000.0
    day = start
    i = 0
    while len(points) < n:
        if day.weekday() < 5:
            points.append({"ts": _ts(day), "strategy_value": value})
            noise = 0.004 * (((i + phase) % 5) - 2) / 2.0
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
    # P1.3b: stubbed gates carry scope-checked execution evidence.
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


def _seed(
    Session,
    *,
    n_points: int = 260,
    drifts: tuple[float, ...] = (0.003, 0.0),
    n_models: int | None = None,
):
    db = Session()
    snapshot = DataSnapshot(
        id=uuid4(), snapshot_key="evidence", provider="fixture", content_sha256="a" * 64
    )
    db.add(snapshot)
    db.flush()
    strategy = Strategy(name="spa", status=StrategyStatus.BACKTESTED)
    db.add(strategy)
    db.flush()
    strategy.family_id = strategy.id
    version = StrategyVersion(strategy_id=strategy.id, version=1, code="print(1)", config={})
    db.add(version)
    db.flush()
    used = drifts if n_models is None else drifts[:n_models]
    backtests: list[Backtest] = []
    for i, drift in enumerate(used):
        backtest = Backtest(
            data_snapshot_id=snapshot.id,
            id=uuid4(),
            strategy_version_id=version.id,
            start_date=date(2018, 1, 1),
            end_date=date(2019, 6, 1),
            status=BacktestStatus.COMPLETED,
            universe_snapshot=[
                {"symbol": "SPY", "effective_from": "2018-01-01", "effective_to": None}
            ],
        )
        db.add(backtest)
        db.flush()
        for point in _long_equity(date(2018, 1, 2), n_points, drift=drift, phase=i * 2):
            db.add(
                BacktestEquity(
                    backtest_id=backtest.id,
                    ts=point["ts"],
                    strategy_value=point["strategy_value"],
                )
            )
        db.add(
            ExperimentTrial(
                data_snapshot_id=snapshot.id,
                backtest_id=backtest.id,
                strategy_id=strategy.id,
                strategy_family=strategy.family_id,
                parameters={"lookback": 100 + i},
                parameter_hash=f"spa-{i}",
            )
        )
        backtests.append(backtest)
    template = backtests[0]
    run = ValidationRun(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        backtest_id=template.id,
        kind=ValidationKind.SPA,
        status=ValidationRunStatus.QUEUED,
        progress_step="Queued",
        params={
            "n_boot": 400,
            "alpha": 0.05,
            "seed": 8,
            "family_id": str(strategy.family_id),
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
        ValidationKind.COST,
        ValidationKind.BOOTSTRAP,
        ValidationKind.REGIME,
    ):
        _add_gate(
            db,
            strategy_id=strategy.id,
            version_id=version.id,
            backtest_id=template.id,
            kind=kind,
        )
    db.commit()
    ids = (str(run.id), strategy.id)
    db.close()
    return ids


def test_spa_strong_best_promotes(monkeypatch):
    Session = _session(monkeypatch)
    from services.worker.tasks import execute_spa

    run_id, strategy_id = _seed(Session, drifts=(0.003, 0.0))
    result = execute_spa(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is True
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run.passed is True
    assert run.result["n_models"] == 2
    assert run.result["p_spa_consistent"] < 0.05
    assert run.result["p_spa_lower"] <= run.result["p_spa_consistent"] + 1e-12
    assert run.result["p_spa_consistent"] <= run.result["p_spa_upper"] + 1e-12
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.VALIDATED
    db.close()


def test_spa_zero_edge_does_not_promote(monkeypatch):
    Session = _session(monkeypatch)
    from services.worker.tasks import execute_spa

    run_id, strategy_id = _seed(Session, drifts=(0.0, 0.0))
    result = execute_spa(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is False
    db = Session()
    run = db.get(ValidationRun, __import__("uuid").UUID(run_id))
    assert run.passed is False
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()


def test_spa_single_trial_fails_loud(monkeypatch):
    Session = _session(monkeypatch)
    from services.worker.tasks import execute_spa

    run_id, strategy_id = _seed(Session, n_models=1, drifts=(0.003,))
    result = execute_spa(run_id)
    assert result["status"] == "FAILED"
    assert "至少需要" in result["error"]
    db = Session()
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()
