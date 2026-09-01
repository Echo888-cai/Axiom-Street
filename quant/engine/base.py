from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

ProgressCallback = Callable[[str], None]


@dataclass
class BacktestRequest:
    backtest_id: str
    strategy_code: str
    strategy_class_name: str
    start_date: date
    end_date: date
    benchmark: str
    initial_capital: float
    parameters: dict[str, Any] = field(default_factory=dict)
    universe: list[str] = field(default_factory=lambda: ["SPY"])
    data_root: Path | None = None
    jobs_root: Path | None = None
    timeout_seconds: int = 1800
    cancel_check: Callable[[], bool] | None = None


@dataclass
class BacktestEngineResult:
    engine_version: str
    data_version: str
    statistics: dict[str, Any]
    equity: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    monthly_returns: list[dict[str, Any]]
    raw_path: str | None = None
    rolling_windows: list[dict[str, Any]] = field(default_factory=list)
    time_series: list[dict[str, Any]] = field(default_factory=list)
    data_snapshot_id: str | None = None


class QuantEngine(ABC):
    @abstractmethod
    def run_backtest(
        self,
        request: BacktestRequest,
        on_progress: ProgressCallback | None = None,
    ) -> BacktestEngineResult:
        raise NotImplementedError

    @abstractmethod
    def cancel_backtest(self, backtest_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        raise NotImplementedError
