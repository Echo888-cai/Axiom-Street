"""Risk gate wrapper smoke (Phase 6 WP-1): fake QCAlgorithm harness outside docker.

Exercises the exact adapter source that gets rendered into the LEAN container:
permissive config must reproduce the ungated order stream exactly; a binding cap
shrinks weights; stop-loss triggers an exit.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from quant.risk.gate import compose_strategy_code, runtime_files
from quant.risk.runtime_gate import build_gate


def _security(price: float, qty: float = 0.0) -> SimpleNamespace:
    return SimpleNamespace(
        HasData=True,
        Price=price,
        Holdings=SimpleNamespace(Quantity=qty, AveragePrice=price),
    )


class _FakeAlgo:
    """Minimal QCAlgorithm look-alike: records SetHoldings, mirrors holdings."""

    def __init__(self, equity: float, prices: dict[str, float]) -> None:
        self.Portfolio = SimpleNamespace(TotalPortfolioValue=equity)
        self.Securities = {symbol: _security(px) for symbol, px in prices.items()}
        self.IsWarmingUp = False
        self.Time = None
        self.orders: list[tuple[str, float]] = []
        self._prices = dict(prices)

    def Initialize(self) -> None:
        pass

    def OnData(self, data: Any) -> None:
        for symbol, weight in getattr(data, "desired", []):
            self.SetHoldings(symbol, weight)

    def SetHoldings(self, symbol: str, weight: float, *_args: Any, **_kwargs: Any) -> None:
        self.orders.append((symbol, weight))

    def _fill_last(self) -> None:
        if not self.orders:
            return
        symbol, weight = self.orders[-1]
        price = self._prices[symbol]
        self.Securities[symbol].Holdings.Quantity = (
            weight * self.Portfolio.TotalPortfolioValue / price
        )
        self.Securities[symbol].Holdings.AveragePrice = price


def _run(algo: _FakeAlgo, desires: list[list[tuple[str, float]]], *, fill: bool) -> None:
    for desired in desires:
        algo.OnData(SimpleNamespace(desired=desired))
        if fill:
            algo._fill_last()


def test_permissive_gate_matches_ungated_order_stream() -> None:
    desires = [[("SPY", 1.0)], [("SPY", 1.0)], [("SPY", 0.0)], [("SPY", 1.0)]]
    prices = {"SPY": 100.0}

    plain = _FakeAlgo(100_000, prices)
    _run(plain, desires, fill=False)

    Gated = build_gate(_FakeAlgo, "{}")
    gated = Gated(100_000, prices)
    _run(gated, desires, fill=False)

    assert gated.orders == plain.orders


def test_position_cap_shrinks_intended_weight() -> None:
    prices = {"SPY": 100.0}
    Gated = build_gate(_FakeAlgo, json.dumps({"max_position_pct": 0.5}))
    gated = Gated(100_000, prices)
    _run(gated, [[("SPY", 1.0)]], fill=True)
    assert gated.orders[-1] == ("SPY", 0.5)
    # Holdings are capped too once filled.
    assert gated.Securities["SPY"].Holdings.Quantity == pytest.approx(0.5 * 100_000 / 100.0)


def test_stop_loss_exits_position() -> None:
    prices = {"SPY": 100.0}
    Gated = build_gate(_FakeAlgo, json.dumps({"stop_loss": 0.05}))
    gated = Gated(100_000, prices)
    # Enter long on bar 1.
    _run(gated, [[("SPY", 1.0)]], fill=True)
    assert gated.orders[-1] == ("SPY", 1.0)
    # Prices drop 6% (> 5%) on the next bar: the stop must exit to 0.
    gated._prices["SPY"] = 94.0
    gated.Securities["SPY"].Price = 94.0
    _run(gated, [[]], fill=False)
    assert gated.orders[-1] == ("SPY", 0.0)


def test_warmup_is_passthrough() -> None:
    prices = {"SPY": 100.0}
    Gated = build_gate(_FakeAlgo, json.dumps({"max_position_pct": 0.5}))
    gated = Gated(100_000, prices)
    gated.IsWarmingUp = True
    _run(gated, [[("SPY", 1.0)]], fill=False)
    assert gated.orders[-1] == ("SPY", 1.0)


def test_rendered_sources_compile_and_compose() -> None:
    import ast
    import py_compile
    import tempfile
    from pathlib import Path

    from quant.strategy_sdk.equal_weight import DEFAULT_EQUAL_WEIGHT_CODE
    from quant.strategy_sdk.spy_200dma import DEFAULT_STRATEGY_CODE

    with tempfile.TemporaryDirectory() as tmp:
        for filename, source in runtime_files().items():
            path = Path(tmp) / filename
            path.write_text(source, encoding="utf-8")
            py_compile.compile(str(path), doraise=True)

    for code, class_name in (
        (DEFAULT_STRATEGY_CODE, "Spy200DmaAlgorithm"),
        (DEFAULT_EQUAL_WEIGHT_CODE, "EqualWeightUniverseAlgorithm"),
    ):
        composed = compose_strategy_code(code, class_name, "{}")
        tree = ast.parse(composed)
        names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        assert class_name in names
        assert f"{class_name}RiskGated" not in names  # assigned via globals(), not a class def
        assert f"{class_name}RiskGated" in composed
        assert code in composed  # user code verbatim
