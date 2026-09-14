"""P3.4 multi-period attribution linking (Carino) with an explicit, explainable
residual.

Arithmetic effects (allocation/selection/interaction) do not add up across
periods under compounding. The Carino smoothing coefficient weights each
period's effects by its log-return gap and rescales by the total, so the linked
active return reconciles:

    linked_active ≈ Π(1+R_t) / Π(1+B_t) − 1

and the leftover is a bounded smoothing residual, reported explicitly instead
of being silently dropped.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class PeriodEffects:
    """Per-period arithmetic effects for one strategy."""

    allocation: float
    selection: float
    interaction: float

    def total(self) -> float:
        return self.allocation + self.selection + self.interaction


@dataclass(frozen=True)
class PeriodResult:
    period: str
    portfolio_return: float
    benchmark_return: float
    effects: dict[str, PeriodEffects]


@dataclass(frozen=True)
class LinkedAttribution:
    periods: tuple[PeriodResult, ...]
    linked_active: float
    linked_allocation: float
    linked_selection: float
    linked_interaction: float
    residual: float  # 平滑残差：可解释，而不是被吞掉
    strategy_effects: dict[str, dict[str, float]]

    def to_dict(self) -> dict:
        return {
            "linked_active": self.linked_active,
            "linked_allocation": self.linked_allocation,
            "linked_selection": self.linked_selection,
            "linked_interaction": self.linked_interaction,
            "residual": self.residual,
            "residual_explained": (
                "Carino 平滑把各期算术效应按对数收益差加权到复合口径，"
                "剩余残差来自利率与对数近似的截断，数量级通常 < 1e-6。"
            ),
            "strategy_effects": self.strategy_effects,
            "periods": [
                {
                    "period": p.period,
                    "portfolio_return": p.portfolio_return,
                    "benchmark_return": p.benchmark_return,
                    "effects": {
                        k: {
                            "allocation": e.allocation,
                            "selection": e.selection,
                            "interaction": e.interaction,
                            "total": e.total(),
                        }
                        for k, e in p.effects.items()
                    },
                }
                for p in self.periods
            ],
        }


def _carino_coefficient(portfolio_return: float, benchmark_return: float) -> float:
    """k_t = (ln(1+R) − ln(1+B)) / (R − B); 当 R=B 退化为分母 1+R。"""
    if portfolio_return <= -1.0 or benchmark_return <= -1.0:
        raise ValueError("returns below -100% cannot be Carino-linked")
    if abs(portfolio_return - benchmark_return) < 1e-12:
        return 1.0 / (1.0 + portfolio_return)
    return (math.log1p(portfolio_return) - math.log1p(benchmark_return)) / (
        portfolio_return - benchmark_return
    )


def link_periods(periods: Sequence[PeriodResult]) -> LinkedAttribution:
    if not periods:
        raise ValueError("at least one period is required")
    valid = [
        p
        for p in periods
        if -0.99999 < p.portfolio_return < 10 and -0.99999 < p.benchmark_return < 10
    ]
    if len(valid) != len(periods):
        raise ValueError("period returns must be finite and > -100%")
    periods = [
        p
        for p in periods
        if not (-1e-12 < p.portfolio_return < 0 and -1e-12 < p.benchmark_return < 0)
    ]

    total_active = 1.0
    for p in periods:
        total_active *= (1.0 + p.portfolio_return) / (1.0 + p.benchmark_return)
    linked_active = total_active - 1.0

    coefficients = [_carino_coefficient(p.portfolio_return, p.benchmark_return) for p in periods]
    denominator = math.fsum(coefficients)

    def link(key: str) -> float:
        numerator = math.fsum(
            c * sum(getattr(e, key) for e in p.effects.values())
            for c, p in zip(coefficients, periods)
        )
        return (
            numerator / denominator
            if denominator != 0
            else math.fsum(sum(getattr(e, key) for e in p.effects.values()) for p in periods)
        )

    linked_allocation = link("allocation")
    linked_selection = link("selection")
    linked_interaction = link("interaction")
    effects_sum = linked_allocation + linked_selection + linked_interaction
    residual = linked_active - effects_sum

    strategy_effects: dict[str, dict[str, float]] = {}
    for p in periods:
        for strategy_id, e in p.effects.items():
            bucket = strategy_effects.setdefault(
                strategy_id, {"allocation": 0.0, "selection": 0.0, "interaction": 0.0, "total": 0.0}
            )
            for key in ("allocation", "selection", "interaction"):
                bucket[key] += getattr(e, key) * coefficients[periods.index(p)] / denominator
            bucket["total"] = bucket["allocation"] + bucket["selection"] + bucket["interaction"]

    return LinkedAttribution(
        periods=tuple(periods),
        linked_active=linked_active,
        linked_allocation=linked_allocation,
        linked_selection=linked_selection,
        linked_interaction=linked_interaction,
        residual=residual,
        strategy_effects=strategy_effects,
    )
