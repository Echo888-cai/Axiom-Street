from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class TargetPosition:
    symbol: str
    quantity: float
    weight: float | None = None


@dataclass
class RiskDecision:
    approved: bool
    targets: list[TargetPosition]
    reasons: list[str]


class RiskEngine(ABC):
    """Phase 1 placeholder — live path must go Strategy → Risk → Execution → Broker."""

    @abstractmethod
    def evaluate(self, targets: list[TargetPosition], context: dict[str, Any]) -> RiskDecision:
        raise NotImplementedError


class PassThroughRiskEngine(RiskEngine):
    def evaluate(self, targets: list[TargetPosition], context: dict[str, Any]) -> RiskDecision:
        return RiskDecision(approved=True, targets=targets, reasons=["phase1_passthrough"])
