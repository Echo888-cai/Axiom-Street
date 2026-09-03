"""Deflated Sharpe Ratio — Bailey & López de Prado (2014), JPM.

DSR is the Probabilistic Sharpe Ratio evaluated at the expected maximum
Sharpe under N independent trials (the selection-bias threshold).

All Sharpe inputs are **per-period** (the same frequency as the returns).
Convert annualized values with ``annualized / sqrt(periods_per_year)``
before calling; do not mix annualized SR with a daily T.
``kurtosis`` is Pearson (Normal = 3), not Fisher's excess.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Sequence

_Z = NormalDist()
_EULER_GAMMA = 0.5772156649015329  # Euler–Mascheroni
_E = math.e
DSR_PASS_THRESHOLD = 0.95


@dataclass(frozen=True)
class DeflatedSharpe:
    observed_sharpe: float
    n_obs: int
    n_trials: int
    trials_stdev: float
    skewness: float
    kurtosis: float
    sr_star: float
    se_sharpe: float
    dsr: float
    psr: float  # PSR against SR*=0 (non-normality only)

    @property
    def passed(self) -> bool:
        return self.dsr >= DSR_PASS_THRESHOLD

    def to_dict(self) -> dict[str, float | int | bool]:
        return {
            "observed_sharpe": self.observed_sharpe,
            "n_obs": self.n_obs,
            "n_trials": self.n_trials,
            "trials_stdev": self.trials_stdev,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "sr_star": self.sr_star,
            "se_sharpe": self.se_sharpe,
            "dsr": self.dsr,
            "psr": self.psr,
            "passed": self.passed,
            "pass_threshold": DSR_PASS_THRESHOLD,
        }


def expected_max_sharpe(n_trials: int, trials_stdev: float, *, mean: float = 0.0) -> float:
    """Eq. (1): E[max SR] after N iid Normal trials.

    For N = 1 the EVT approximation is undefined (Φ^{-1}(0)); the selection
    threshold is the mean (0 under the null of no skill).
    """
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")
    if trials_stdev < 0:
        raise ValueError("trials_stdev must be >= 0")
    if n_trials == 1 or trials_stdev == 0.0:
        return mean
    max_z = (1.0 - _EULER_GAMMA) * _Z.inv_cdf(1.0 - 1.0 / n_trials) + _EULER_GAMMA * _Z.inv_cdf(
        1.0 - 1.0 / (n_trials * _E)
    )
    return mean + trials_stdev * max_z


def probabilistic_sharpe_ratio(
    observed_sharpe: float,
    n_obs: int,
    *,
    sr_threshold: float = 0.0,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Bailey & López de Prado (2012) PSR: P(true SR > sr_threshold)."""
    se = _sharpe_standard_error(observed_sharpe, n_obs, skewness, kurtosis)
    if se == 0.0:
        return 1.0 if observed_sharpe > sr_threshold else 0.0
    return _Z.cdf((observed_sharpe - sr_threshold) / se)


def _sharpe_standard_error(
    observed_sharpe: float, n_obs: int, skewness: float, kurtosis: float
) -> float:
    if n_obs < 2:
        raise ValueError("n_obs must be >= 2")
    if kurtosis <= 0:
        raise ValueError("kurtosis must be Pearson kurtosis (> 0); Normal = 3")
    denom = 1.0 - skewness * observed_sharpe + ((kurtosis - 1.0) / 4.0) * observed_sharpe**2
    if denom <= 0:
        raise ValueError(
            f"non-normal Sharpe variance is non-positive (skew={skewness}, kurtosis={kurtosis})"
        )
    return math.sqrt(denom / (n_obs - 1))


def deflated_sharpe_ratio(
    observed_sharpe: float,
    n_obs: int,
    n_trials: int,
    trials_stdev: float,
    *,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> DeflatedSharpe:
    """Eq. (2): DSR = PSR(SR*) with SR* = E[max SR | N, σ]."""
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1 — the trial ledger is the denominator")
    sr_star = expected_max_sharpe(n_trials, trials_stdev)
    se = _sharpe_standard_error(observed_sharpe, n_obs, skewness, kurtosis)
    dsr = probabilistic_sharpe_ratio(
        observed_sharpe,
        n_obs,
        sr_threshold=sr_star,
        skewness=skewness,
        kurtosis=kurtosis,
    )
    psr = probabilistic_sharpe_ratio(
        observed_sharpe,
        n_obs,
        sr_threshold=0.0,
        skewness=skewness,
        kurtosis=kurtosis,
    )
    return DeflatedSharpe(
        observed_sharpe=observed_sharpe,
        n_obs=n_obs,
        n_trials=n_trials,
        trials_stdev=trials_stdev,
        skewness=skewness,
        kurtosis=kurtosis,
        sr_star=sr_star,
        se_sharpe=se,
        dsr=dsr,
        psr=psr,
    )


def pearson_kurtosis(excess_kurtosis: float) -> float:
    """Convert Fisher excess kurtosis (pandas default) to Pearson (Normal = 3)."""
    return float(excess_kurtosis) + 3.0


def annualized_to_per_period(sharpe: float, periods_per_year: float) -> float:
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    return sharpe / math.sqrt(periods_per_year)


def trials_stdev_from_sharpes(sharpes: Sequence[float]) -> float:
    """Sample standard deviation of trial Sharpes. N=1 → 0 (no selection variance)."""
    values = [float(x) for x in sharpes]
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(var)
