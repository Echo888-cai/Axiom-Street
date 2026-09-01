/** Keep in sync with quant/strategy_sdk/spy_200dma.py */
export const SPY_200DMA_TEMPLATE = `from AlgorithmImports import *


class Spy200DmaAlgorithm(QCAlgorithm):
    """SPY 200DMA trend strategy.

    Hypothesis: SPY above its 200-day SMA indicates a risk-on regime worth holding;
    below indicates risk-off and cash is preferred.

    Execution: signal at daily close, fill on the next daily bar, 5 bps slippage.
    """

    def Initialize(self):
        start = self.GetParameter("start_date")
        end = self.GetParameter("end_date")
        capital = self.GetParameter("initial_capital")

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

        self.spy = self.AddEquity("SPY", Resolution.Daily)
        self.spy.SetDataNormalizationMode(DataNormalizationMode.Adjusted)
        self.SetBenchmark("SPY")

        self.sma = self.SMA(self.spy.Symbol, 200, Resolution.Daily)
        self.SetWarmUp(200)

        # 5 bps slippage + flat fee
        self.spy.SetSlippageModel(ConstantSlippageModel(0.0005))
        self.spy.SetFeeModel(ConstantFeeModel(1.0))

        # Pending target from prior bar close; executed next bar.
        self._pending_target = None

    def OnData(self, data):
        if self.IsWarmingUp or not self.sma.IsReady:
            return
        if self.spy.Symbol not in data.Bars:
            return

        # 1) Execute yesterday's signal on today's bar
        if self._pending_target is not None:
            self.SetHoldings(self.spy.Symbol, self._pending_target)

        # 2) Compute today's close signal for tomorrow
        price = float(self.Securities[self.spy.Symbol].Close)
        sma = float(self.sma.Current.Value)
        self._pending_target = 1.0 if price > sma else 0.0
`;
