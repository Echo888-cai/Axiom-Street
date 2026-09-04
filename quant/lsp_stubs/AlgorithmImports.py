"""Minimal QuantConnect stubs for Jedi completion in the strategy lab.

These are not executed. They exist so ``from AlgorithmImports import *``
resolves QCAlgorithm / Resolution / models without the LEAN image on the API.
"""

from typing import Any, Optional


class Resolution:
    Daily = "Daily"
    Hour = "Hour"
    Minute = "Minute"
    Second = "Second"
    Tick = "Tick"


class DataNormalizationMode:
    Adjusted = "Adjusted"
    Raw = "Raw"
    TotalReturn = "TotalReturn"
    SplitAdjusted = "SplitAdjusted"


class SecurityType:
    Equity = "Equity"


class Symbol:
    Value: str = ""


class TradeBar:
    Time: Any = None
    Open: float = 0.0
    High: float = 0.0
    Low: float = 0.0
    Close: float = 0.0
    Volume: float = 0.0


class Slice:
    Bars: dict = {}
    Time: Any = None

    def __contains__(self, symbol: Any) -> bool:
        return False

    def __getitem__(self, symbol: Any) -> Any:
        return None


class Indicator:
    IsReady: bool = False
    Current: Any = None


class Security:
    Symbol: Symbol = Symbol()
    Close: float = 0.0

    def SetDataNormalizationMode(self, mode: Any) -> None:
        return None

    def SetSlippageModel(self, model: Any) -> None:
        return None

    def SetFeeModel(self, model: Any) -> None:
        return None


class ConstantSlippageModel:
    def __init__(self, slippage: float) -> None:
        self.slippage = slippage


class ConstantFeeModel:
    def __init__(self, fee: float) -> None:
        self.fee = fee


class QCAlgorithm:
    """LEAN Python algorithm base class (stub)."""

    Securities: dict = {}
    Portfolio: Any = None
    Time: Any = None
    IsWarmingUp: bool = False

    def Initialize(self) -> None:
        return None

    def OnData(self, data: Slice) -> None:
        return None

    def GetParameter(self, name: str, default_value: Optional[str] = None) -> Optional[str]:
        return default_value

    def SetStartDate(self, year: int, month: int, day: int) -> None:
        return None

    def SetEndDate(self, year: int, month: int, day: int) -> None:
        return None

    def SetCash(self, cash: float) -> None:
        return None

    def SetBenchmark(self, symbol: Any) -> None:
        return None

    def SetWarmUp(self, bars: int) -> None:
        return None

    def AddEquity(self, ticker: str, resolution: Any = None) -> Security:
        return Security()

    def SMA(self, symbol: Any, period: int, resolution: Any = None) -> Indicator:
        return Indicator()

    def EMA(self, symbol: Any, period: int, resolution: Any = None) -> Indicator:
        return Indicator()

    def SetHoldings(self, symbol: Any, percentage: float) -> None:
        return None

    def Liquidate(self, symbol: Any = None) -> None:
        return None

    def Log(self, message: str) -> None:
        return None

    def Debug(self, message: str) -> None:
        return None

    def Error(self, message: str) -> None:
        return None


__all__ = [
    "QCAlgorithm",
    "Resolution",
    "DataNormalizationMode",
    "SecurityType",
    "Symbol",
    "TradeBar",
    "Slice",
    "Security",
    "ConstantSlippageModel",
    "ConstantFeeModel",
]
