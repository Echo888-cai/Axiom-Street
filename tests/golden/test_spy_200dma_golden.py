"""Golden backtest for SPY 200DMA.

Requires Docker + pinned LEAN image. Expectations are filled after the first
successful frozen run and then locked.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from quant.engine.base import BacktestRequest
from quant.engine.lean import LeanQuantEngine
from quant.strategy_sdk.spy_200dma import DEFAULT_STRATEGY_CLASS, DEFAULT_STRATEGY_CODE

GOLDEN_DIR = Path(__file__).parent / "spy_200dma"
EXPECTATIONS = GOLDEN_DIR / "expectations.json"


@pytest.mark.golden
def test_spy_200dma_golden_backtest():
    if not EXPECTATIONS.exists():
        pytest.skip("Golden expectations not frozen yet — run once with Docker to seed")

    expectations = json.loads(EXPECTATIONS.read_text(encoding="utf-8"))
    repo_root = Path(__file__).resolve().parents[2]
    data_root = Path(os.getenv("AXIOM_DATA_ROOT", repo_root / "data"))
    # Colima can only bind-mount paths under the user home; avoid /var/folders tmp.
    jobs_root = Path(os.getenv("AXIOM_JOBS_ROOT", repo_root / "jobs" / "golden"))
    jobs_root.mkdir(parents=True, exist_ok=True)

    if not (data_root / "market" / "equities" / "US" / "daily" / "SPY.parquet").exists():
        pytest.skip("SPY parquet missing — run python -m quant.data.ingest_spy")

    engine = LeanQuantEngine(data_root=data_root, jobs_root=jobs_root)
    health = engine.health_check()
    if not health.get("docker_available"):
        pytest.skip("Docker / LEAN image not available")

    from datetime import date

    result = engine.run_backtest(
        BacktestRequest(
            backtest_id="golden-spy-200dma",
            strategy_code=DEFAULT_STRATEGY_CODE,
            strategy_class_name=DEFAULT_STRATEGY_CLASS,
            start_date=date.fromisoformat(expectations["start_date"]),
            end_date=date.fromisoformat(expectations["end_date"]),
            benchmark="SPY",
            initial_capital=100_000,
        )
    )

    metrics = result.statistics
    assert metrics["trade_count"] == expectations["trade_count"]
    assert abs(metrics["final_equity"] - expectations["final_equity"]) < expectations.get(
        "equity_tol", 1.0
    )
    assert abs(metrics["max_drawdown"] - expectations["max_drawdown"]) < expectations.get(
        "dd_tol", 1e-3
    )
    assert abs(metrics["sharpe"] - expectations["sharpe"]) < expectations.get("sharpe_tol", 1e-2)

    # Reproducibility: second run must match first
    result2 = engine.run_backtest(
        BacktestRequest(
            backtest_id="golden-spy-200dma-2",
            strategy_code=DEFAULT_STRATEGY_CODE,
            strategy_class_name=DEFAULT_STRATEGY_CLASS,
            start_date=date.fromisoformat(expectations["start_date"]),
            end_date=date.fromisoformat(expectations["end_date"]),
            benchmark="SPY",
            initial_capital=100_000,
        )
    )
    assert result2.statistics["trade_count"] == metrics["trade_count"]
    assert abs(result2.statistics["final_equity"] - metrics["final_equity"]) < 1e-6
