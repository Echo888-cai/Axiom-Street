from __future__ import annotations

from pathlib import Path

import pytest

from quant.engine.pool import LeanSlotPool


def test_warm_slot_command_uses_security_policy(monkeypatch, tmp_path: Path):
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stderr = ""

    def fake_run(command, **_kwargs):
        calls.append(command)
        return Result()

    monkeypatch.setattr("quant.engine.pool.subprocess.run", fake_run)
    pool = LeanSlotPool(
        image="lean:test",
        size=1,
        jobs_root=tmp_path / "jobs",
        data_root=tmp_path / "data",
        warm=True,
    )

    pool._start_warm()

    start = calls[-1]
    assert "--read-only" in start
    assert start[start.index("--network") + 1] == "none"


def test_unsafe_strategy_is_rejected_before_job_directory_is_created(tmp_path: Path):
    from datetime import date

    from quant.engine.base import BacktestRequest
    from quant.engine.lean import LeanQuantEngine
    from quant.security.sandbox import StrategySandboxViolation

    jobs = tmp_path / "jobs"
    request = BacktestRequest(
        backtest_id="unsafe",
        strategy_code="import os\nclass Demo: pass\n",
        strategy_class_name="Demo",
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 2),
        benchmark="SPY",
        initial_capital=100_000,
        jobs_root=jobs,
        data_root=tmp_path / "data",
    )

    with pytest.raises(StrategySandboxViolation, match="strategy_sandbox_violation"):
        LeanQuantEngine(data_root=tmp_path / "data", jobs_root=jobs).run_backtest(request)
    assert not (jobs / "unsafe").exists()
