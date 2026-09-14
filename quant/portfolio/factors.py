"""P3.4 factor regression ledger: every recorded exposure carries its model,
data source and frequency; nothing is fabricated when there is no factor data.

The API only stores regressions that were actually computed (or declared with
full provenance). Listing returns only recorded entries — an empty list is an
honest "no factor data", never a made-up exposure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

MIN_OBS = 5


@dataclass(frozen=True)
class FactorRegression:
    model: str = "OLS"
    source: str = "computed"
    frequency: str = "monthly"
    alpha: float = 0.0
    r2: float = 0.0
    n_obs: int = 0
    exposures: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "source": self.source,
            "frequency": self.frequency,
            "alpha": self.alpha,
            "r2": self.r2,
            "n_obs": self.n_obs,
            "exposures": dict(self.exposures or {}),
        }


def estimate_ols_exposures(
    *,
    excess_returns: Sequence[float],
    factor_returns: dict[str, Sequence[float]],
    frequency: str = "monthly",
) -> FactorRegression:
    """OLS beta / alpha / R² of portfolio excess returns on factor returns.

    Raises if inputs are inconsistent or too short to estimate anything except
    noise — an "exposure" without enough observations is a fabrication.
    """
    if len(excess_returns) < MIN_OBS:
        raise ValueError(f"需要至少 {MIN_OBS} 期收益才能估计因子暴露，当前 {len(excess_returns)}")
    if not factor_returns:
        raise ValueError("没有因子数据：不能虚构暴露")
    lengths = {len(v) for v in factor_returns.values()}
    lengths.add(len(excess_returns))
    if len(lengths) != 1:
        raise ValueError("超额收益与各因子序列长度必须一致")

    y = np.asarray(excess_returns, dtype=float)
    factor_names = sorted(factor_returns)
    design = np.column_stack([np.asarray(factor_returns[n], dtype=float) for n in factor_names])
    ones = np.ones((len(y), 1))
    X = np.hstack([ones, design])
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    predicted = X @ beta
    ss_res = float(np.sum((y - predicted) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    if not math.isfinite(r2):
        r2 = 0.0

    exposures = {name: float(beta[1 + i]) for i, name in enumerate(factor_names)}
    return FactorRegression(
        model="OLS",
        source="computed",
        frequency=frequency,
        alpha=float(beta[0]),
        r2=float(np.clip(r2, 0.0, 1.0)),
        n_obs=len(y),
        exposures=exposures,
    )
