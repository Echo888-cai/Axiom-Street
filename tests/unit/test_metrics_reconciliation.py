"""Cross-check Axiom metrics against LEAN-reported statistics.

LEAN's Sharpe/Sortino default to a 1% risk-free rate. Axiom defaults to 0%
(configurable via ``risk_free_rate``). CAGR and max drawdown do not depend on
that assumption and are compared directly.

Tolerances (docs/PHASE-1.5.md WP-1):
Sharpe ±0.05, CAGR ±0.1 percentage points, MaxDD ±0.5 percentage points.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quant.engine.result_parser import parse_lean_result
from quant.metrics.performance import parse_money, parse_pct

FIXTURE = Path(__file__).parent / "fixtures" / "lean_spy_200dma_2018_2020.json"

SHARPE_TOL = 0.05
CAGR_TOL = 0.001  # 0.1 percentage points as a fraction
DD_TOL = 0.005  # 0.5 percentage points as a fraction
LEAN_DEFAULT_RF = 0.01


@pytest.mark.skipif(not FIXTURE.exists(), reason="LEAN fixture missing")
def test_axiom_metrics_reconcile_with_lean_statistics():
    parsed = parse_lean_result(FIXTURE)
    metrics = parsed["metrics"]
    lean = parsed["statistics"]

    lean_cagr = parse_pct(lean["Compounding Annual Return"])
    lean_dd = parse_pct(lean["Drawdown"])
    assert lean_cagr is not None
    assert lean_dd is not None
    if lean_dd > 0:
        lean_dd = -lean_dd

    assert abs(metrics["cagr"] - lean_cagr) <= CAGR_TOL
    assert abs(metrics["max_drawdown"] - lean_dd) <= DD_TOL
    assert abs(metrics["calmar"] - metrics["cagr"] / abs(metrics["max_drawdown"])) < 1e-12
    assert metrics["commission"] == parse_money(lean["Total Fees"])
    assert metrics["extras"]["lean_statistics"]["Sharpe Ratio"] == lean["Sharpe Ratio"]
    assert metrics["extras"]["risk_free_rate"] == 0.0

    # Match LEAN's default Rf so Sharpe is an apples-to-apples sentinel.
    aligned = parse_lean_result(FIXTURE, risk_free_rate=LEAN_DEFAULT_RF)["metrics"]
    lean_sharpe = parse_pct(lean["Sharpe Ratio"])
    assert lean_sharpe is not None
    assert abs(aligned["sharpe"] - lean_sharpe) <= SHARPE_TOL
    lean_sortino = parse_pct(lean.get("Sortino Ratio"))
    if lean_sortino is not None:
        assert abs(aligned["sortino"] - lean_sortino) <= SHARPE_TOL


@pytest.mark.skipif(not FIXTURE.exists(), reason="LEAN fixture missing")
def test_reconciliation_fixture_has_daily_equity():
    parsed = parse_lean_result(FIXTURE)
    assert len(parsed["equity"]) > 500
    assert parsed["metrics"]["final_equity"] is not None
    lean_end = parsed["statistics"].get("End Equity")
    if lean_end is not None:
        assert abs(parsed["metrics"]["final_equity"] - parse_money(lean_end)) < 1.0


def test_fixture_json_is_valid():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert "Statistics" in data or "statistics" in data
    assert "Charts" in data or "charts" in data
