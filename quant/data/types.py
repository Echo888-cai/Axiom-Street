from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ProviderCapabilities:
    ohlcv: bool
    dividends: bool
    splits: bool
    point_in_time: bool

    @property
    def corporate_actions(self) -> bool:
        return self.dividends and self.splits


YFINANCE_CAPABILITIES = ProviderCapabilities(
    ohlcv=True, dividends=True, splits=True, point_in_time=False
)
STOOQ_CAPABILITIES = ProviderCapabilities(
    ohlcv=True, dividends=False, splits=False, point_in_time=False
)

CAPABILITIES_BY_SOURCE = {
    "yfinance": YFINANCE_CAPABILITIES,
    "yahoo": YFINANCE_CAPABILITIES,
    "stooq": STOOQ_CAPABILITIES,
}


@dataclass
class FetchResult:
    frame: Any
    source: str
    capabilities: ProviderCapabilities


class ProviderCapabilityError(RuntimeError):
    """Raised when a provider cannot support the requested backtest mode."""


class DataQualityError(RuntimeError):
    def __init__(self, message: str, report: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.report = report or {}


@dataclass
class QualityIssue:
    rule: str
    severity: str  # blocking | warning
    message: str
    count: int = 1
    examples: list[Any] = field(default_factory=list)


@dataclass
class DataQualityReport:
    issues: list[QualityIssue]
    row_count: int
    start: datetime | None
    end: datetime | None

    @property
    def has_blocking_issues(self) -> bool:
        return any(i.severity == "blocking" for i in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_count": self.row_count,
            "start": self.start.isoformat() if self.start is not None else None,
            "end": self.end.isoformat() if self.end is not None else None,
            "has_blocking_issues": self.has_blocking_issues,
            "issues": [
                {
                    "rule": i.rule,
                    "severity": i.severity,
                    "message": i.message,
                    "count": i.count,
                    "examples": i.examples[:5],
                }
                for i in self.issues
            ],
        }
