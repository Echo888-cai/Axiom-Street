"""P3.3 acceptance: the validation plan states applicability, sample needs,
parameter-read requirements and resource estimates before anything runs.

"样本不足" / "参数未被读取" must make a gate inapplicable (an equal-curve scan
must not pass), and the frozen out-of-sample range comes from the reference
backtest.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone


def _seed(db, *, code: str, days: int, trials: int):
    from services.api.models import (
        Backtest,
        BacktestEquity,
        BacktestStatus,
        ExperimentTrial,
        Strategy,
        StrategyStatus,
        StrategyVersion,
    )

    strategy = Strategy(name=f"plan-{uuid.uuid4().hex[:6]}", status=StrategyStatus.BACKTESTED)
    db.add(strategy)
    db.flush()
    strategy.family_id = strategy.id
    version = StrategyVersion(
        strategy_id=strategy.id, version=1, code=code, config={}, created_by="local"
    )
    db.add(version)
    db.flush()
    backtest = Backtest(
        id=uuid.uuid4(),
        strategy_version_id=version.id,
        start_date=date(2020, 1, 1),
        end_date=date(2021, 12, 31),
        status=BacktestStatus.COMPLETED,
        universe_snapshot=[],
        finished_at=datetime(2021, 12, 31, tzinfo=timezone.utc),
    )
    db.add(backtest)
    db.flush()
    for i in range(days):
        db.add(
            BacktestEquity(
                backtest_id=backtest.id,
                ts=datetime(2020, 1, 1, tzinfo=timezone.utc),
                strategy_value=100_000.0 + i,
            )
        )
    for i in range(trials):
        db.add(
            ExperimentTrial(
                strategy_family=strategy.family_id,
                strategy_id=strategy.id,
                parameter_hash=f"h{i}",
                observed_sharpe=0.5 + i * 0.01,
                parameters={"lookback": 200 + i},
                data_snapshot_id=None,
            )
        )
    db.commit()
    return version.id, backtest.id


def _plan_for(client, monkeypatch, *, code: str, days: int, trials: int):
    from services.api import db as db_module

    db = db_module.SessionLocal()
    try:
        version_id, backtest_id = _seed(db, code=code, days=days, trials=trials)
    finally:
        db.close()
    res = client.get(
        f"/api/v1/validation/plan?strategy_version_id={version_id}&backtest_id={backtest_id}"
    )
    assert res.status_code == 200, res.text
    return res.json()


TREND_CODE = """from AlgorithmImports import *
class A(QCAlgorithm):
    def Initialize(self):
        self.GetParameter("lookback")
        self.GetParameter("slippage_bps")
"""


def test_short_sample_makes_bootstrap_inapplicable(client, monkeypatch):
    plan = _plan_for(client, monkeypatch, code=TREND_CODE, days=126, trials=3)
    gate = next(g for g in plan["gates"] if g["kind"] == "BOOTSTRAP")
    assert gate["applicable"] is False
    assert gate["reason_code"] == "insufficient_samples"
    assert "252" in gate["reason"]
    assert plan["trading_days"] == 126


def test_parameter_not_read_blocks_scans(client, monkeypatch):
    code_without_lookback = """from AlgorithmImports import *
class A(QCAlgorithm):
    def Initialize(self):
        pass
"""
    plan = _plan_for(client, monkeypatch, code=code_without_lookback, days=504, trials=3)
    for kind in ("PBO", "SENSITIVITY"):
        gate = next(g for g in plan["gates"] if g["kind"] == kind)
        assert gate["applicable"] is False
        assert gate["reason_code"] == "parameter_not_read"
        assert "GetParameter" in gate["reason"]
        assert gate["estimate"]["lean_runs"] == 0


def test_scan_estimate_counts_lean_runs(client, monkeypatch):
    plan = _plan_for(client, monkeypatch, code=TREND_CODE, days=504, trials=3)
    pbo = next(g for g in plan["gates"] if g["kind"] == "PBO")
    assert pbo["applicable"] is True
    assert pbo["supported_operators"] == ["lookback"]
    assert pbo["estimate"]["lean_runs"] >= 1
    assert plan["totals"]["lean_runs"] >= pbo["estimate"]["lean_runs"]
    assert plan["totals"]["gates_applicable"] <= plan["totals"]["gates_total"]


def test_spa_needs_two_trials_and_frozen_window_is_reported(client, monkeypatch):
    plan = _plan_for(client, monkeypatch, code=TREND_CODE, days=504, trials=1)
    spa = next(g for g in plan["gates"] if g["kind"] == "SPA")
    assert spa["applicable"] is False
    assert spa["reason_code"] == "insufficient_trials"
    assert plan["frozen"]["start"] == "2020-01-01"
    assert plan["frozen"]["end"] == "2021-12-31"
    assert "冻结" in plan["frozen"]["note"]


def test_walk_forward_requires_train_plus_test_years(client, monkeypatch):
    short = _plan_for(client, monkeypatch, code=TREND_CODE, days=300, trials=2)
    wf = next(g for g in short["gates"] if g["kind"] == "WALK_FORWARD")
    assert wf["applicable"] is False
    assert wf["reason_code"] == "insufficient_samples"
    long = _plan_for(client, monkeypatch, code=TREND_CODE, days=1200, trials=2)
    wf_long = next(g for g in long["gates"] if g["kind"] == "WALK_FORWARD")
    assert wf_long["applicable"] is True
    assert wf_long["estimate"]["lean_runs"] >= 1
