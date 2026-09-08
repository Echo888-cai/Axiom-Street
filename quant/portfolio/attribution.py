"""Single-period Brinson attribution with explicit inputs."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Sequence

_WEIGHT_TOLERANCE = 1e-9


@dataclass(frozen=True)
class AttributionObservation:
    strategy_id: str
    weight: float
    strategy_return: float
    benchmark_return: float


@dataclass(frozen=True)
class AttributionContribution:
    strategy_id: str
    weight: float
    benchmark_weight: float
    strategy_return: float
    benchmark_return: float
    allocation_effect: float
    selection_effect: float
    interaction_effect: float


@dataclass(frozen=True)
class AttributionResult:
    portfolio_return: float
    benchmark_return: float
    allocation_effect: float
    selection_effect: float
    interaction_effect: float
    active_return: float
    contributions: tuple[AttributionContribution, ...]

    def to_dict(self) -> dict:
        return {
            "portfolio_return": self.portfolio_return,
            "benchmark_return": self.benchmark_return,
            "allocation_effect": self.allocation_effect,
            "selection_effect": self.selection_effect,
            "interaction_effect": self.interaction_effect,
            "active_return": self.active_return,
            "contributions": [asdict(row) for row in self.contributions],
        }


def _finite(value: float, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def compute_brinson_attribution(
    observations: Sequence[AttributionObservation],
) -> AttributionResult:
    if not observations:
        raise ValueError("attribution observations must not be empty")
    seen: set[str] = set()
    normalized: list[AttributionObservation] = []
    for observation in observations:
        strategy_id = str(observation.strategy_id).strip()
        if not strategy_id:
            raise ValueError("strategy_id must not be empty")
        if strategy_id in seen:
            raise ValueError(f"duplicate strategy_id: {strategy_id}")
        seen.add(strategy_id)
        weight = _finite(observation.weight, "weights")
        strategy_return = _finite(observation.strategy_return, "strategy_return")
        benchmark_return = _finite(observation.benchmark_return, "benchmark_return")
        if weight < 0:
            raise ValueError("weights must be non-negative")
        normalized.append(
            AttributionObservation(strategy_id, weight, strategy_return, benchmark_return)
        )
    total_weight = sum(row.weight for row in normalized)
    if abs(total_weight - 1.0) > _WEIGHT_TOLERANCE:
        raise ValueError(f"weights must sum to 1, got {total_weight}")

    benchmark_weight = 1.0 / len(normalized)
    contributions: list[AttributionContribution] = []
    for row in normalized:
        allocation = (row.weight - benchmark_weight) * row.benchmark_return
        selection = benchmark_weight * (row.strategy_return - row.benchmark_return)
        interaction = (row.weight - benchmark_weight) * (row.strategy_return - row.benchmark_return)
        contributions.append(
            AttributionContribution(
                strategy_id=row.strategy_id,
                weight=row.weight,
                benchmark_weight=benchmark_weight,
                strategy_return=row.strategy_return,
                benchmark_return=row.benchmark_return,
                allocation_effect=allocation,
                selection_effect=selection,
                interaction_effect=interaction,
            )
        )
    portfolio_return = sum(row.weight * row.strategy_return for row in normalized)
    benchmark_return = sum(benchmark_weight * row.benchmark_return for row in normalized)
    allocation_effect = sum(row.allocation_effect for row in contributions)
    selection_effect = sum(row.selection_effect for row in contributions)
    interaction_effect = sum(row.interaction_effect for row in contributions)
    active_return = portfolio_return - benchmark_return
    if not math.isclose(
        active_return,
        allocation_effect + selection_effect + interaction_effect,
        rel_tol=0,
        abs_tol=1e-12,
    ):
        raise ValueError("attribution decomposition does not reconcile")
    return AttributionResult(
        portfolio_return=portfolio_return,
        benchmark_return=benchmark_return,
        allocation_effect=allocation_effect,
        selection_effect=selection_effect,
        interaction_effect=interaction_effect,
        active_return=active_return,
        contributions=tuple(contributions),
    )
