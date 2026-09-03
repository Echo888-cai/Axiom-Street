"""Equal-weight cross-sectional baseline for a point-in-time universe.

Fill convention matches SPY 200DMA: signal on this bar, fill next bar,
5 bps slippage, $1 flat fee. Monthly reconstitution.
"""

from __future__ import annotations

from quant.data.symbols import normalize_symbols

DEFAULT_EQUAL_WEIGHT_CLASS = "EqualWeightUniverseAlgorithm"

# Ten liquid US-listed names used when the lab loads the template.
# The live backtest universe still comes from the snapshot / 标的池.
DEFAULT_EQUAL_WEIGHT_UNIVERSE = [
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "EFA",
    "EEM",
    "TLT",
    "GLD",
    "XLE",
    "XLF",
]


def parse_universe_parameter(raw: str | None) -> list[str]:
    if raw is None or not str(raw).strip():
        raise ValueError("universe parameter is empty")
    return normalize_symbols(str(raw).replace(";", ","))


def equal_weight_targets(symbols: list[str] | str) -> dict[str, float]:
    """1/N weights. Empty input fails loud — never a silent 0% book."""
    tickers = normalize_symbols(symbols)
    weight = 1.0 / float(len(tickers))
    return {symbol: weight for symbol in tickers}


def equal_weight_builder_config(symbols: list[str] | None = None) -> dict:
    tickers = list(symbols or DEFAULT_EQUAL_WEIGHT_UNIVERSE)
    return {
        "class_name": DEFAULT_EQUAL_WEIGHT_CLASS,
        "hypothesis": "等权 1/N 是任何主动叠加必须在成本后击败的横截面基线。",
        "universe": {
            "asset_class": "equity",
            "market": "US",
            "symbols": tickers,
            "universe_filter": "equal_weight",
        },
        "signal": {
            "entry_signal": "hold every current constituent",
            "exit_signal": "drop names that leave the point-in-time universe",
            "lookback_period": None,
            "rebalance_frequency": "monthly",
        },
        "position_sizing": {
            "model": "equal_weight",
            "target_weight": round(1.0 / len(tickers), 6),
        },
        "risk": {
            "max_position_pct": round(1.0 / len(tickers), 6),
            "stop_loss": None,
            "portfolio_drawdown_halt": None,
        },
        "execution": {
            "rebalance": "next_bar",
            "slippage_bps": 5,
            "commission": "constant_1_usd",
        },
    }


DEFAULT_EQUAL_WEIGHT_CODE = '''from AlgorithmImports import *


class EqualWeightUniverseAlgorithm(QCAlgorithm):
    """Equal-weight the current universe; rebalance monthly on the next bar.

    Hypothesis: 1/N across names that are actually members this month is the
    baseline any active overlay must beat after costs.

    Execution: signal at daily close, fill on the next daily bar, 5 bps slippage.
    """

    def Initialize(self):
        start = self.GetParameter("start_date")
        end = self.GetParameter("end_date")
        capital = self.GetParameter("initial_capital")
        raw = self.GetParameter("universe")

        if start:
            y, m, d = [int(x) for x in start.split("-")]
            self.SetStartDate(y, m, d)
        else:
            self.SetStartDate(2015, 1, 1)

        if end:
            y, m, d = [int(x) for x in end.split("-")]
            self.SetEndDate(y, m, d)
        else:
            self.SetEndDate(2024, 12, 31)

        self.SetCash(float(capital) if capital else 100000)

        if not raw:
            raise ValueError("universe parameter is required")
        tickers = [part.strip().upper() for part in raw.replace(";", ",").split(",") if part.strip()]
        if not tickers:
            raise ValueError("universe parameter is empty")

        raw_slippage = self.GetParameter("slippage_bps")
        slippage_bps = float(raw_slippage) if raw_slippage else 5.0
        raw_fee = self.GetParameter("fee_usd")
        fee_usd = float(raw_fee) if raw_fee else 1.0

        self._symbols = []
        for ticker in tickers:
            equity = self.AddEquity(ticker, Resolution.Daily)
            equity.SetDataNormalizationMode(DataNormalizationMode.Adjusted)
            equity.SetSlippageModel(ConstantSlippageModel(slippage_bps / 10000.0))
            equity.SetFeeModel(ConstantFeeModel(fee_usd))
            self._symbols.append(equity.Symbol)

        self.SetBenchmark(tickers[0])
        self._month_key = None
        self._pending = None

    def OnData(self, data):
        if self._pending is not None:
            for symbol, weight in self._pending.items():
                if self.Securities.ContainsKey(symbol) and self.Securities[symbol].HasData:
                    self.SetHoldings(symbol, weight)
            self._pending = None

        key = (self.Time.year, self.Time.month)
        if key == self._month_key:
            return
        self._month_key = key

        live = [symbol for symbol in self._symbols if symbol in data.Bars]
        if not live:
            return
        weight = 1.0 / float(len(live))
        self._pending = {symbol: weight for symbol in live}
'''
