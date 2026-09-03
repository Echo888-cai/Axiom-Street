"""Seeded SPY 200-day moving average strategy for Phase 1.

Fill convention (documented for Golden Backtest):
- Signal is evaluated on the current daily bar close.
- Target is applied on the *next* daily bar (avoids same-bar look-ahead).
- Slippage: 5 bps via ConstantSlippageModel.
"""

from __future__ import annotations

DEFAULT_STRATEGY_CLASS = "Spy200DmaAlgorithm"

DEFAULT_STRATEGY_CODE = '''from AlgorithmImports import *


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

        raw_lookback = self.GetParameter("lookback")
        lookback = int(raw_lookback) if raw_lookback else 200
        self.sma = self.SMA(self.spy.Symbol, lookback, Resolution.Daily)
        self.SetWarmUp(lookback)

        raw_slippage = self.GetParameter("slippage_bps")
        slippage_bps = float(raw_slippage) if raw_slippage else 5.0
        raw_fee = self.GetParameter("fee_usd")
        fee_usd = float(raw_fee) if raw_fee else 1.0
        self.spy.SetSlippageModel(ConstantSlippageModel(slippage_bps / 10000.0))
        self.spy.SetFeeModel(ConstantFeeModel(fee_usd))

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
'''


def default_builder_config() -> dict:
    return {
        "class_name": DEFAULT_STRATEGY_CLASS,
        "hypothesis": "SPY 站上 200 日均线代表风险偏好，持有；跌破则空仓。",
        "universe": {
            "asset_class": "equity",
            "market": "US",
            "symbols": ["SPY"],
            "universe_filter": "single_asset",
        },
        "signal": {
            "entry_signal": "close > SMA(200)",
            "exit_signal": "close <= SMA(200)",
            "lookback_period": 200,
            "rebalance_frequency": "daily",
        },
        "position_sizing": {
            "model": "all_in_or_cash",
            "target_weight": 1.0,
        },
        "risk": {
            "max_position_pct": 1.0,
            "stop_loss": None,
            "portfolio_drawdown_halt": None,
        },
        "execution": {
            "rebalance": "next_bar",
            "slippage_bps": 5,
            "commission": "constant_1_usd",
        },
    }
