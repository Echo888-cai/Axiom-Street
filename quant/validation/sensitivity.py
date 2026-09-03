"""Parameter-sensitivity surface: knife-edge vs plateau.

This is a product rule, not a named statistical test. Given a 1-D grid of
observed Sharpes, the peak is a **knife-edge** when it is the only point
within ``drop_tolerance`` Sharpe of the maximum — a classic overfitting
signature. A **plateau** requires at least ``min_plateau_width`` consecutive
grid points (including the peak) inside that band.

Identical equity paths fail loud: the scan parameter was not read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

DROP_TOLERANCE = 0.5
MIN_PLATEAU_WIDTH = 3
MIN_GRID = 3
MAX_GRID = 12


class SensitivityError(ValueError):
    """Fail-loud sensitivity-grid errors."""


@dataclass(frozen=True)
class GridPoint:
    value: float
    sharpe: float
    backtest_id: str | None = None
    on_plateau: bool = False
    is_peak: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "value": self.value,
            "sharpe": self.sharpe,
            "backtest_id": self.backtest_id,
            "on_plateau": self.on_plateau,
            "is_peak": self.is_peak,
        }


@dataclass(frozen=True)
class SensitivityResult:
    passed: bool
    shape: str
    reason: str
    peak_value: float
    peak_sharpe: float
    plateau_width: int
    neighbor_drop: float
    drop_tolerance: float
    min_plateau_width: int
    points: list[GridPoint]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "shape": self.shape,
            "reason": self.reason,
            "peak_value": self.peak_value,
            "peak_sharpe": self.peak_sharpe,
            "plateau_width": self.plateau_width,
            "neighbor_drop": self.neighbor_drop,
            "drop_tolerance": self.drop_tolerance,
            "min_plateau_width": self.min_plateau_width,
            "points": [p.to_dict() for p in self.points],
        }


def classify_surface(
    values: Sequence[float],
    sharpes: Sequence[float | None],
    *,
    backtest_ids: Sequence[str | None] | None = None,
    drop_tolerance: float = DROP_TOLERANCE,
    min_plateau_width: int = MIN_PLATEAU_WIDTH,
) -> SensitivityResult:
    """Classify a 1-D Sharpe grid. ``values`` must be strictly sorted unique numbers."""
    if drop_tolerance <= 0:
        raise SensitivityError("drop_tolerance 必须 > 0")
    if min_plateau_width < 2:
        raise SensitivityError("min_plateau_width 必须 >= 2")
    if len(values) != len(sharpes):
        raise SensitivityError("参数值与 Sharpe 长度不一致")
    if len(values) < MIN_GRID:
        raise SensitivityError(f"敏感性网格至少需要 {MIN_GRID} 个点")
    if len(values) > MAX_GRID:
        raise SensitivityError(f"敏感性网格最多 {MAX_GRID} 个点")
    if len(set(values)) != len(values):
        raise SensitivityError("网格参数值必须互异")
    ordered_pairs = sorted(zip(values, range(len(values))), key=lambda item: item[0])
    if any(ordered_pairs[i][0] >= ordered_pairs[i + 1][0] for i in range(len(ordered_pairs) - 1)):
        raise SensitivityError("网格参数值必须严格递增")

    ids = list(backtest_ids) if backtest_ids is not None else [None] * len(values)
    if len(ids) != len(values):
        raise SensitivityError("backtest_ids 长度与网格不一致")

    parsed: list[float] = []
    for sharpe in sharpes:
        if sharpe is None:
            raise SensitivityError("网格存在缺失的 Sharpe，拒绝分类")
        number = float(sharpe)
        if number != number:  # NaN
            raise SensitivityError("网格存在非有限 Sharpe，拒绝分类")
        parsed.append(number)

    # Ties: the most central peak by parameter value, so a flat ridge is not a spike.
    max_sharpe = max(parsed)
    tied = [i for i, s in enumerate(parsed) if s == max_sharpe]
    tied_by_value = sorted(tied, key=lambda i: values[i])
    peak_idx = tied_by_value[len(tied_by_value) // 2]
    peak_value = float(values[peak_idx])
    peak_sharpe = parsed[peak_idx]

    sorted_idx = [i for _, i in ordered_pairs]
    peak_rank = sorted_idx.index(peak_idx)
    lo = peak_rank
    hi = peak_rank
    while lo > 0 and parsed[sorted_idx[lo - 1]] >= peak_sharpe - drop_tolerance:
        lo -= 1
    while hi < len(sorted_idx) - 1 and parsed[sorted_idx[hi + 1]] >= peak_sharpe - drop_tolerance:
        hi += 1
    plateau_members = set(sorted_idx[lo : hi + 1])
    plateau_width = hi - lo + 1

    neighbors: list[float] = []
    if peak_rank > 0:
        neighbors.append(parsed[sorted_idx[peak_rank - 1]])
    if peak_rank < len(sorted_idx) - 1:
        neighbors.append(parsed[sorted_idx[peak_rank + 1]])
    neighbor_drop = float(peak_sharpe - min(neighbors)) if neighbors else 0.0

    points = [
        GridPoint(
            value=float(values[i]),
            sharpe=parsed[i],
            backtest_id=ids[i],
            on_plateau=i in plateau_members,
            is_peak=i == peak_idx,
        )
        for i in sorted_idx
    ]

    if peak_sharpe <= 0:
        return SensitivityResult(
            passed=False,
            shape="knife_edge",
            reason="峰值 Sharpe ≤ 0，没有可稳健的 edge。",
            peak_value=peak_value,
            peak_sharpe=peak_sharpe,
            plateau_width=plateau_width,
            neighbor_drop=neighbor_drop,
            drop_tolerance=drop_tolerance,
            min_plateau_width=min_plateau_width,
            points=points,
        )

    if plateau_width >= min_plateau_width:
        return SensitivityResult(
            passed=True,
            shape="plateau",
            reason=(
                f"峰值 lookback={_fmt(peak_value)} 的 Sharpe {peak_sharpe:.2f} 周围有 "
                f"{plateau_width} 个点落在 {drop_tolerance:.2f} 带宽内，判定为高原。"
            ),
            peak_value=peak_value,
            peak_sharpe=peak_sharpe,
            plateau_width=plateau_width,
            neighbor_drop=neighbor_drop,
            drop_tolerance=drop_tolerance,
            min_plateau_width=min_plateau_width,
            points=points,
        )

    return SensitivityResult(
        passed=False,
        shape="knife_edge",
        reason=(
            f"峰值 lookback={_fmt(peak_value)} 的 Sharpe {peak_sharpe:.2f} 仅有 "
            f"{plateau_width} 个点落在 {drop_tolerance:.2f} 带宽内（需要 ≥{min_plateau_width}），"
            f"邻点下落 {neighbor_drop:.2f}，判定为孤峰。"
        ),
        peak_value=peak_value,
        peak_sharpe=peak_sharpe,
        plateau_width=plateau_width,
        neighbor_drop=neighbor_drop,
        drop_tolerance=drop_tolerance,
        min_plateau_width=min_plateau_width,
        points=points,
    )


def assert_navs_differ(finals: Sequence[float | None]) -> None:
    """Same check as return-matrix identity, using terminal NAV only."""
    parsed: list[float] = []
    for value in finals:
        if value is None:
            raise SensitivityError("缺少期末净值，拒绝判断路径是否可区分")
        parsed.append(float(value))
    if len(parsed) < 2:
        raise SensitivityError("至少需要 2 个期末净值")
    if max(parsed) - min(parsed) < 1e-8:
        raise SensitivityError(
            "各参数的净值无法区分。策略很可能没有读取扫描参数，拒绝把敏感性算成通过。"
        )



def _fmt(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


DEFAULT_LOOKBACK_GRID = (100, 150, 200, 250, 300)
