"""Cost sensitivity: one-way cost (bps) where CAPM alpha hits zero.

The sweep puts the entire one-way cost into ``slippage_bps`` so the
breakeven is a well-defined bps number — not a mix of $1/ticket and bps.
``fee_usd`` is set to 0 when the strategy reads it.

Breakeven is the smallest cost at which ``alpha_capm`` ≤ 0, linearly
interpolated from the previous grid point. If that number is at or below
the universe's realistic one-way cost, the strategy is dead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from quant.validation.sensitivity import SensitivityError, assert_navs_differ

SLIPPAGE_PARAMETER = "slippage_bps"
FEE_PARAMETER = "fee_usd"
DEFAULT_COSTS_BPS = (0.0, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0)
DEFAULT_REALISTIC_BPS = 5.0
MIN_GRID = 3
MAX_GRID = 12


class CostSensitivityError(ValueError):
    """Fail-loud cost-grid errors."""


@dataclass(frozen=True)
class CostPoint:
    cost_bps: float
    alpha_capm: float
    sharpe: float | None
    backtest_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "cost_bps": self.cost_bps,
            "alpha_capm": self.alpha_capm,
            "sharpe": self.sharpe,
            "backtest_id": self.backtest_id,
        }


@dataclass(frozen=True)
class CostSensitivityResult:
    passed: bool
    reason: str
    breakeven_bps: float | None
    breakeven_kind: str
    realistic_one_way_bps: float
    conclusion: str
    points: list[CostPoint]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "breakeven_bps": self.breakeven_bps,
            "breakeven_kind": self.breakeven_kind,
            "realistic_one_way_bps": self.realistic_one_way_bps,
            "conclusion": self.conclusion,
            "points": [p.to_dict() for p in self.points],
        }


def interpolate_breakeven(
    costs: Sequence[float],
    alphas: Sequence[float],
) -> tuple[float | None, str]:
    """Smallest cost where alpha ≤ 0. ``None`` means still positive at the grid max."""
    if len(costs) != len(alphas):
        raise CostSensitivityError("成本网格与 alpha 长度不一致")
    if len(costs) < 2:
        raise CostSensitivityError("盈亏平衡至少需要 2 个成本点")
    if any(costs[i] >= costs[i + 1] for i in range(len(costs) - 1)):
        raise CostSensitivityError("成本网格必须严格递增")
    if costs[0] < 0:
        raise CostSensitivityError("成本不能为负")

    if alphas[0] <= 0:
        if costs[0] != 0:
            raise CostSensitivityError(
                f"网格从 {costs[0]:g} bps 起 alpha 已非正，无法求临界成本。请把 0 bps 纳入网格。"
            )
        return 0.0, "nonpositive_at_floor"

    for i in range(1, len(costs)):
        if alphas[i] > 0:
            continue
        prev_a = float(alphas[i - 1])
        curr_a = float(alphas[i])
        prev_c = float(costs[i - 1])
        curr_c = float(costs[i])
        if prev_a == curr_a:
            return curr_c, "crossed_without_slope"
        frac = prev_a / (prev_a - curr_a)
        if frac < 0 or frac > 1:
            raise CostSensitivityError("alpha 插值超出相邻成本区间，拒绝外推")
        return prev_c + frac * (curr_c - prev_c), "interpolated"
    return None, "above_grid"


def classify_cost_curve(
    costs: Sequence[float],
    alphas: Sequence[float | None],
    *,
    sharpes: Sequence[float | None] | None = None,
    backtest_ids: Sequence[str | None] | None = None,
    realistic_one_way_bps: float = DEFAULT_REALISTIC_BPS,
) -> CostSensitivityResult:
    if realistic_one_way_bps < 0:
        raise CostSensitivityError("真实单边成本不能为负")
    if len(costs) < MIN_GRID:
        raise CostSensitivityError(f"成本网格至少需要 {MIN_GRID} 个点")
    if len(costs) > MAX_GRID:
        raise CostSensitivityError(f"成本网格最多 {MAX_GRID} 个点")
    if len(set(costs)) != len(costs):
        raise CostSensitivityError("成本点必须互异")
    parsed: list[float] = []
    for alpha in alphas:
        if alpha is None:
            raise CostSensitivityError("网格存在缺失的 alpha_capm，拒绝求临界成本")
        number = float(alpha)
        if number != number:
            raise CostSensitivityError("网格存在非有限 alpha_capm，拒绝求临界成本")
        parsed.append(number)

    ids = list(backtest_ids) if backtest_ids is not None else [None] * len(costs)
    sr = list(sharpes) if sharpes is not None else [None] * len(costs)
    if len(ids) != len(costs) or len(sr) != len(costs):
        raise CostSensitivityError("backtest_ids / sharpes 长度与网格不一致")

    ordered = sorted(zip(costs, parsed, sr, ids), key=lambda row: row[0])
    ordered_costs = [float(row[0]) for row in ordered]
    ordered_alphas = [float(row[1]) for row in ordered]
    points = [
        CostPoint(
            cost_bps=float(cost),
            alpha_capm=float(alpha),
            sharpe=None if sharpe is None else float(sharpe),
            backtest_id=bt_id,
        )
        for cost, alpha, sharpe, bt_id in ordered
    ]

    breakeven, kind = interpolate_breakeven(ordered_costs, ordered_alphas)
    if breakeven is None:
        ceiling = ordered_costs[-1]
        conclusion = f"该策略在单边成本超过 {ceiling:g} bps 时仍有正 alpha（网格上限）。"
        return CostSensitivityResult(
            passed=True,
            reason=f"网格最高 {ceiling:g} bps 处 alpha 仍为正，临界成本在网格之上。",
            breakeven_bps=None,
            breakeven_kind=kind,
            realistic_one_way_bps=float(realistic_one_way_bps),
            conclusion=conclusion,
            points=points,
        )

    conclusion = f"该策略在单边成本超过 {breakeven:.2f} bps 时失效。"
    if breakeven <= realistic_one_way_bps:
        return CostSensitivityResult(
            passed=False,
            reason=(
                f"临界成本 {breakeven:.2f} bps ≤ 真实单边成本 "
                f"{realistic_one_way_bps:g} bps，策略即刻判死。"
            ),
            breakeven_bps=float(breakeven),
            breakeven_kind=kind,
            realistic_one_way_bps=float(realistic_one_way_bps),
            conclusion=conclusion,
            points=points,
        )
    return CostSensitivityResult(
        passed=True,
        reason=(f"临界成本 {breakeven:.2f} bps 高于真实单边成本 {realistic_one_way_bps:g} bps。"),
        breakeven_bps=float(breakeven),
        breakeven_kind=kind,
        realistic_one_way_bps=float(realistic_one_way_bps),
        conclusion=conclusion,
        points=points,
    )


def assert_cost_paths_differ(finals: Sequence[float | None], *, traded: bool) -> None:
    """If the strategy traded, 0 bps vs max bps must move NAV. Else cost is unbound."""
    if not traded:
        return
    try:
        assert_navs_differ(finals)
    except SensitivityError as exc:
        raise CostSensitivityError(
            "各成本点净值无法区分。策略很可能没有读取 slippage_bps，拒绝把成本敏感性算成通过。"
        ) from exc
