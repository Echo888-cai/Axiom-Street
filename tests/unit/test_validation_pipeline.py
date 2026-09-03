"""Phase 3 §5.4 — full validation pipeline acceptance.

Per-gate unit tests already exist. This file asks the product questions:

- A brute-force lookback search on SPY (the dual-MA / price-vs-SMA family)
  must surface PBO > 0.5 and a DSR that is deflated below the raw Sharpe
  story. VALIDATED stays system-owned.
- A 200DMA-like weak but consistent edge must *not* look like overfitting.
  The locked golden CAGR of ~1.3% is the honest baseline, not a fake alpha.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from quant.engine.base import BacktestEngineResult
from quant.metrics.deflated_sharpe import DSR_PASS_THRESHOLD
from quant.metrics.performance import compute_metrics_from_equity
from quant.strategy_sdk.spy_200dma import DEFAULT_STRATEGY_CODE
from services.api.db import Base
from services.api.models import (
    Backtest,
    BacktestEquity,
    BacktestMetrics,
    BacktestStatus,
    Strategy,
    StrategyStatus,
    StrategyVersion,
    ValidationKind,
    ValidationRun,
    ValidationRunStatus,
)
from services.api.status_machine import assert_client_status_transition

_GOLDEN_EXPECTATIONS = (
    Path(__file__).resolve().parents[1] / "golden" / "spy_200dma" / "expectations.json"
)
_OVERFIT_LOOKBACKS = (80, 100, 120, 150, 180, 200, 220, 250)
_DMA_LOOKBACKS = (100, 150, 200, 250, 300)


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


class _PipelineEngine:
    """Synthetic dual-MA lookback search. No LEAN — returns are the fixture."""

    def __init__(self, **_kwargs) -> None:
        self.pattern = "overfit"
        self.requests: list = []

    def cancel_backtest(self, _backtest_id: str) -> None:
        return None

    def run_backtest(self, request, on_progress=None) -> BacktestEngineResult:
        self.requests.append(request)
        if on_progress:
            on_progress("Running algorithm")
        lookback = int((request.parameters or {}).get("lookback") or 200)

        def ret_fn(i: int) -> float:
            if self.pattern == "overfit":
                column = {value: idx for idx, value in enumerate(_OVERFIT_LOOKBACKS)}[lookback]
                extra = 0.0
                if column * 10 <= i < column * 10 + 10:
                    extra = 0.05
                opposite = ((column + 4) % 8) * 10
                if opposite <= i < opposite + 10:
                    extra = -0.05
                return 0.0003 + extra + column * 1e-5
            # Weak, persistent drift — 200DMA-like, not a CSCV trap.
            noise = 0.004 * ((i % 5) - 2) / 2.0
            drift = 0.00004 - (lookback - 200) * 2e-7
            return drift + noise

        equity = _equity(request.start_date, 81, ret_fn=ret_fn)
        metrics = compute_metrics_from_equity(equity, trade_count=0)
        return BacktestEngineResult(
            engine_version="quantconnect/lean:16355",
            data_version="abc",
            statistics=metrics,
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


def _seed(Session, *, values: tuple[int, ...], stub_other_gates: bool) -> tuple[str, UUID, UUID]:
    db = Session()
    strategy = Strategy(name="pipeline", status=StrategyStatus.BACKTESTED)
    db.add(strategy)
    db.flush()
    strategy.family_id = strategy.id
    version = StrategyVersion(
        strategy_id=strategy.id,
        version=1,
        code=DEFAULT_STRATEGY_CODE,
        config={"class_name": "Spy200DmaAlgorithm"},
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
        kind=ValidationKind.PBO,
        status=ValidationRunStatus.QUEUED,
        progress_step="Queued",
        params={
            "parameter_key": "lookback",
            "values": list(values),
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
    if stub_other_gates:
        for kind in (
            ValidationKind.WALK_FORWARD,
            ValidationKind.DSR,
            ValidationKind.SENSITIVITY,
            ValidationKind.COST,
            ValidationKind.BOOTSTRAP,
            ValidationKind.REGIME,
            ValidationKind.SPA,
        ):
            _add_gate(
                db,
                strategy_id=strategy.id,
                version_id=version.id,
                backtest_id=backtest.id,
                kind=kind,
            )
    db.commit()
    ids = (str(run.id), strategy.id, version.id)
    db.close()
    return ids


def _record_dsr_on_best(Session, run_id: str) -> ValidationRun:
    from services.api.services.validation import maybe_apply_validated, record_dsr_for_backtest

    db = Session()
    pbo = db.get(ValidationRun, UUID(run_id))
    assert pbo is not None
    scan_ids = [UUID(item) for item in pbo.result["backtest_ids"]]
    rows = [db.get(BacktestMetrics, item) for item in scan_ids]
    best = max(rows, key=lambda row: float(row.sharpe or 0.0))
    backtest = db.get(Backtest, best.backtest_id)
    n_obs = (
        db.query(BacktestEquity).filter(BacktestEquity.backtest_id == backtest.id).count() - 1
    )
    record_dsr_for_backtest(
        db,
        backtest,
        {
            "sharpe": best.sharpe,
            "skewness": best.skewness,
            "kurtosis": best.kurtosis,
        },
        n_obs=n_obs,
    )
    maybe_apply_validated(
        db, strategy_id=pbo.strategy_id, strategy_version_id=pbo.strategy_version_id
    )
    db.commit()
    dsr = db.scalars(
        select(ValidationRun)
        .where(
            ValidationRun.kind == ValidationKind.DSR,
            ValidationRun.backtest_id == backtest.id,
        )
        .order_by(ValidationRun.created_at.desc())
    ).first()
    assert dsr is not None
    db.expunge(dsr)
    db.close()
    return dsr


def test_overfit_dual_ma_search_flags_pbo_and_deflates_dsr(monkeypatch):
    Session = _session(monkeypatch)
    fake = _PipelineEngine()
    fake.pattern = "overfit"
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_pbo_scan

    run_id, strategy_id, _version_id = _seed(
        Session, values=_OVERFIT_LOOKBACKS, stub_other_gates=True
    )
    result = execute_pbo_scan(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is False

    db = Session()
    pbo = db.get(ValidationRun, UUID(run_id))
    assert float(pbo.result["pbo"]) > 0.5
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()

    dsr = _record_dsr_on_best(Session, run_id)
    assert dsr.error is None
    assert dsr.result["n_trials"] == len(_OVERFIT_LOOKBACKS)
    assert dsr.result["dsr"] < dsr.result["psr"]
    assert dsr.result["dsr"] < DSR_PASS_THRESHOLD
    assert dsr.passed is False

    db = Session()
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    with pytest.raises(HTTPException) as exc:
        assert_client_status_transition(strategy.status, StrategyStatus.VALIDATED)
    assert exc.value.status_code == 409
    db.close()


def test_spy_200dma_like_pipeline_is_weak_edge_not_overfit(monkeypatch):
    Session = _session(monkeypatch)
    fake = _PipelineEngine()
    fake.pattern = "dma"
    monkeypatch.setattr("services.worker.tasks.LeanQuantEngine", lambda **_k: fake)
    from services.worker.tasks import execute_pbo_scan

    run_id, strategy_id, _version_id = _seed(
        Session, values=_DMA_LOOKBACKS, stub_other_gates=False
    )
    result = execute_pbo_scan(run_id)
    assert result["status"] == "COMPLETED"
    assert result["passed"] is True

    db = Session()
    pbo = db.get(ValidationRun, UUID(run_id))
    assert float(pbo.result["pbo"]) <= 0.5
    strategy = db.get(Strategy, strategy_id)
    # Other VALIDATED gates were never run — weak edge is not a free pass.
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()

    dsr = _record_dsr_on_best(Session, run_id)
    assert dsr.error is None
    assert dsr.result["n_trials"] == len(_DMA_LOOKBACKS)
    # Annualized Sharpe of this weak synthetic is not a 2.5 fishing trophy.
    assert dsr.result["observed_sharpe_annualized"] < 1.0

    db = Session()
    strategy = db.get(Strategy, strategy_id)
    assert strategy.status == StrategyStatus.BACKTESTED
    db.close()


def test_golden_spy_200dma_baseline_is_weak_not_spectacular():
    expectations = json.loads(_GOLDEN_EXPECTATIONS.read_text(encoding="utf-8"))
    assert expectations["cagr"] == pytest.approx(0.01308, abs=1e-5)
    assert expectations["sharpe"] == pytest.approx(0.136, abs=0.02)
    assert expectations["final_equity"] > 100_000
    assert expectations["final_equity"] < 110_000
