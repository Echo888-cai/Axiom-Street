"""Probability of Backtest Overfitting via CSCV — Bailey et al. (2015).

Combinatorially Symmetric Cross-Validation: split the return matrix into S
even slices, enumerate every combination of S/2 slices as the in-sample set,
pick the IS-best configuration, and ask whether its OOS rank is below the
median. PBO is that fraction.

PBO > 0.5 means the selected configuration underperforms the median trial
out of sample more often than not.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PBOResult:
    pbo: float
    n_combinations: int
    n_configs: int
    n_slices: int
    n_obs: int
    logit_lambda: list[float]

    @property
    def passed(self) -> bool:
        return self.pbo <= 0.5

    def to_dict(self) -> dict[str, object]:
        return {
            "pbo": self.pbo,
            "n_combinations": self.n_combinations,
            "n_configs": self.n_configs,
            "n_slices": self.n_slices,
            "n_obs": self.n_obs,
            "passed": self.passed,
        }


def combinatorially_symmetric_cv(
    returns: np.ndarray,
    *,
    n_slices: int = 16,
) -> PBOResult:
    """``returns`` is shape (T, N) — rows = time, columns = trial configurations.

    Performance statistic is the Sharpe of each column on the IS / OOS subset.
    S must be even and divide T.
    """
    matrix = np.asarray(returns, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("returns must be a 2-D array of shape (T, n_configs)")
    n_obs, n_configs = matrix.shape
    if n_configs < 2:
        raise ValueError("CSCV requires at least 2 configurations")
    if n_slices < 2 or n_slices % 2 != 0:
        raise ValueError("n_slices must be an even integer >= 2")
    if n_obs < n_slices:
        raise ValueError("not enough observations to form the requested slices")
    if n_obs % n_slices != 0:
        raise ValueError(
            f"T={n_obs} is not divisible by S={n_slices}; refuse to drop leftover bars"
        )

    slice_len = n_obs // n_slices
    slices = [matrix[i * slice_len : (i + 1) * slice_len] for i in range(n_slices)]
    half = n_slices // 2
    ranks: list[float] = []
    for is_idx in itertools.combinations(range(n_slices), half):
        oos_idx = tuple(i for i in range(n_slices) if i not in is_idx)
        is_block = np.concatenate([slices[i] for i in is_idx], axis=0)
        oos_block = np.concatenate([slices[i] for i in oos_idx], axis=0)
        is_sharpe = _column_sharpes(is_block)
        oos_sharpe = _column_sharpes(oos_block)
        winner = int(np.argmax(is_sharpe))
        # Relative rank of the IS-best on OOS: 0 = worst, 1 = best.
        oos_rank = _relative_rank(oos_sharpe, winner)
        ranks.append(oos_rank)

    # λ_oos < 1/2  ⇔  IS-best finished in the bottom half OOS.
    below = sum(1 for rank in ranks if rank < 0.5)
    pbo = below / len(ranks)
    logits = [_logit(rank) for rank in ranks]
    return PBOResult(
        pbo=pbo,
        n_combinations=len(ranks),
        n_configs=n_configs,
        n_slices=n_slices,
        n_obs=n_obs,
        logit_lambda=logits,
    )


def _column_sharpes(block: np.ndarray) -> np.ndarray:
    means = block.mean(axis=0)
    stds = block.std(axis=0, ddof=1)
    out = np.zeros(block.shape[1], dtype=float)
    ok = stds > 0
    out[ok] = means[ok] / stds[ok]
    return out


def _relative_rank(values: np.ndarray, index: int) -> float:
    """Portion of configs with strictly lower OOS Sharpe, plus half of ties.

    Returns 0 for last place, 1 for first place. Median is 0.5.
    """
    n = len(values)
    if n <= 1:
        return 0.5
    target = values[index]
    below = float(np.sum(values < target))
    ties = float(np.sum(values == target) - 1)
    return (below + 0.5 * ties) / (n - 1)


def _logit(rank: float) -> float:
    clipped = min(max(rank, 1e-12), 1.0 - 1e-12)
    return math.log(clipped / (1.0 - clipped))


LOOKBACK_PARAMETER = "lookback"
_MIN_SLICE_BARS = 10
_SLICE_CANDIDATES = (16, 14, 12, 10, 8, 6, 4)


class PBOScanError(ValueError):
    """Fail-loud parameter-scan / return-matrix errors."""


def strategy_reads_parameter(code: str, key: str) -> bool:
    """True iff the algorithm reads ``GetParameter(key)``. Quote-bearing keys are rejected."""
    if not key or '"' in key or "'" in key:
        return False
    return f'GetParameter("{key}")' in code or f"GetParameter('{key}')" in code


def strategy_reads_lookback(code: str) -> bool:
    return strategy_reads_parameter(code, LOOKBACK_PARAMETER)


def daily_returns_from_equity(equity: list[dict]) -> tuple[list[str], np.ndarray]:
    """Return ISO dates (of the later bar) and simple returns. Fail if NAV hits 0."""
    if len(equity) < 2:
        raise PBOScanError("净值不足 2 根，无法计算日收益")
    ordered = sorted(equity, key=lambda p: str(p["ts"]))
    dates: list[str] = []
    rets: list[float] = []
    prev = float(ordered[0]["strategy_value"])
    for point in ordered[1:]:
        current = float(point["strategy_value"])
        if prev == 0:
            raise PBOScanError("净值出现 0，拒绝计算 PBO")
        ts = point["ts"]
        dates.append(str(ts)[:10] if not hasattr(ts, "isoformat") else ts.isoformat()[:10])
        rets.append(current / prev - 1.0)
        prev = current
    return dates, np.asarray(rets, dtype=float)


def align_return_matrix(
    series: list[tuple[list[str], np.ndarray]],
) -> tuple[list[str], np.ndarray]:
    """Intersect dates across configurations. Refuse to pad or drop silently inside a config."""
    if len(series) < 2:
        raise PBOScanError("PBO 至少需要 2 组参数的收益序列")
    common = None
    by_date: list[dict[str, float]] = []
    for dates, rets in series:
        if len(dates) != len(rets):
            raise PBOScanError("日期与收益长度不一致")
        mapping = dict(zip(dates, rets.tolist()))
        by_date.append(mapping)
        keys = set(mapping)
        common = keys if common is None else common & keys
    if not common:
        raise PBOScanError("各参数回测没有共同交易日，拒绝对齐")
    ordered = sorted(common)
    if len(ordered) < _MIN_SLICE_BARS * 4:
        raise PBOScanError(f"共同交易日只有 {len(ordered)} 天，不足以做 CSCV")
    matrix = np.column_stack([[row[d] for d in ordered] for row in by_date])
    return ordered, matrix


def assert_configs_differ(matrix: np.ndarray) -> None:
    """Refuse PBO when the scan parameter was ignored (identical paths)."""
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        raise PBOScanError("收益矩阵列数不足")
    cum = np.cumprod(1.0 + matrix, axis=0)
    finals = cum[-1]
    spread = float(np.max(finals) - np.min(finals))
    if spread < 1e-8:
        raise PBOScanError(
            "各参数的净值无法区分。策略很可能没有读取扫描参数，拒绝把 PBO 算成通过。"
        )


def choose_n_slices(n_obs: int) -> int:
    for n_slices in _SLICE_CANDIDATES:
        if n_obs >= n_slices * _MIN_SLICE_BARS and n_obs % n_slices == 0:
            return n_slices
    raise PBOScanError(
        f"T={n_obs} 不能整除 4–16 的偶数份且每份不少于 {_MIN_SLICE_BARS} 根。"
        "拒绝丢弃交易日来凑 CSCV。"
    )
