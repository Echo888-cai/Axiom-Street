/** Keep in sync with quant/strategy_sdk/equal_weight.py */
export const EQUAL_WEIGHT_TEMPLATE = `from AlgorithmImports import *


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

        self._symbols = []
        for ticker in tickers:
            equity = self.AddEquity(ticker, Resolution.Daily)
            equity.SetDataNormalizationMode(DataNormalizationMode.Adjusted)
            equity.SetSlippageModel(ConstantSlippageModel(0.0005))
            equity.SetFeeModel(ConstantFeeModel(1.0))
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
`;

export const EQUAL_WEIGHT_CONFIG = {
  class_name: "EqualWeightUniverseAlgorithm",
  hypothesis: "等权 1/N 是任何主动叠加必须在成本后击败的横截面基线。",
  universe: {
    asset_class: "equity",
    market: "US",
    symbols: ["SPY", "QQQ", "IWM", "DIA", "EFA", "EEM", "TLT", "GLD", "XLE", "XLF"],
    universe_filter: "equal_weight",
  },
  signal: {
    entry_signal: "hold every current constituent",
    exit_signal: "drop names that leave the point-in-time universe",
    lookback_period: null,
    rebalance_frequency: "monthly",
  },
  position_sizing: {
    model: "equal_weight",
    target_weight: 0.1,
  },
  risk: {
    max_position_pct: 0.1,
    stop_loss: null,
    portfolio_drawdown_halt: null,
  },
  execution: {
    rebalance: "next_bar",
    slippage_bps: 5,
    commission: "constant_1_usd",
  },
};
