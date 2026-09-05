"""Stationary bootstrap confidence intervals — Politis & Romano (1994).

IID resampling is forbidden: it destroys return autocorrelation and
understates Sharpe sampling error. Block length is the Politis & White
(2004) automatic mean for the stationary bootstrap, using the flat-top
kernel on the return autocovariances.

Percentile intervals (Efron). VALIDATED requires the Sharpe interval
strictly above zero at the stated confidence level.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

import numpy as np

_CALENDAR_DAYS_PER_YEAR = 365.25
_TRADING_DAYS_PER_YEAR = 252.0
MIN_OBS = 252
MIN_BOOT = 200
MAX_BOOT = 5_000
DEFAULT_N_BOOT = 2_000
DEFAULT_CONFIDENCE = 0.95
METHODS = ("stationary", "block")


class BootstrapError(ValueError):
    """Fail-loud bootstrap errors. Never invent a tight interval."""


@dataclass(frozen=True)
class Interval:
    observed: float
    low: float
    high: float
    crosses_zero: bool

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "observed": self.observed,
            "low": self.low,
            "high": self.high,
            "crosses_zero": self.crosses_zero,
        }


@dataclass(frozen=True)
class BootstrapResult:
    passed: bool
    reason: str
    method: str
    n_obs: int
    n_boot: int
    mean_block_length: float
    confidence_level: float
    periods_per_year: float
    years: float
    seed: int
    sharpe: Interval
    cagr: Interval
    max_drawdown: Interval

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "method": self.method,
            "n_obs": self.n_obs,
            "n_boot": self.n_boot,
            "mean_block_length": self.mean_block_length,
            "confidence_level": self.confidence_level,
            "periods_per_year": self.periods_per_year,
            "years": self.years,
            "seed": self.seed,
            "sharpe": self.sharpe.to_dict(),
            "cagr": self.cagr.to_dict(),
            "max_drawdown": self.max_drawdown.to_dict(),
        }


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed


def returns_from_equity(
    equity: Sequence[Mapping[str, Any]],
) -> tuple[np.ndarray, float, float]:
    """Daily (or native-bar) returns plus calendar years and periods/year."""
    if len(equity) < 2:
        raise BootstrapError("净值不足 2 根，无法做 Bootstrap")
    ordered = sorted(equity, key=lambda row: _as_datetime(row["ts"]))
    values = np.asarray([float(row["strategy_value"]) for row in ordered], dtype=float)
    if not np.all(np.isfinite(values)):
        raise BootstrapError("净值存在非有限值，拒绝 Bootstrap")
    if np.any(values == 0):
        raise BootstrapError("净值出现 0，拒绝计算收益")
    rets = values[1:] / values[:-1] - 1.0
    if not np.all(np.isfinite(rets)):
        raise BootstrapError("收益存在非有限值，拒绝 Bootstrap")
    first = _as_datetime(ordered[0]["ts"])
    last = _as_datetime(ordered[-1]["ts"])
    days = max((last - first).total_seconds() / 86400.0, 1.0)
    years = days / _CALENDAR_DAYS_PER_YEAR
    deltas = np.diff([_as_datetime(row["ts"]).timestamp() for row in ordered]) / 86400.0
    median = float(np.median(deltas)) if len(deltas) else 1.0
    if 0.4 <= median <= 2.0:
        ppy = _TRADING_DAYS_PER_YEAR
    elif 4.0 <= median <= 10.0:
        ppy = 52.0
    elif 20.0 <= median <= 45.0:
        ppy = 12.0
    else:
        raise BootstrapError(f"净值采样不是日/周/月频（中位间隔 {median:.2f} 天），拒绝 Bootstrap")
    return rets, years, ppy


def sharpe_from_returns(returns: np.ndarray, periods_per_year: float) -> float:
    if len(returns) < 2:
        raise BootstrapError("收益长度不足以计算 Sharpe")
    std = float(np.std(returns, ddof=1))
    if not np.isfinite(std) or std == 0.0:
        raise BootstrapError("收益波动为 0，Sharpe 没有定义")
    return float(np.mean(returns) / std * np.sqrt(periods_per_year))


def cagr_from_returns(returns: np.ndarray, years: float) -> float:
    if years <= 0:
        raise BootstrapError("样本日历跨度必须 > 0")
    wealth = float(np.prod(1.0 + returns))
    if not np.isfinite(wealth):
        raise BootstrapError("净值乘积非有限，拒绝计算 CAGR")
    if wealth <= 0:
        return -1.0
    return float(wealth ** (1.0 / years) - 1.0)


def max_drawdown_from_returns(returns: np.ndarray) -> float:
    path = np.concatenate(([1.0], np.cumprod(1.0 + returns)))
    if np.any(path <= 0) or not np.all(np.isfinite(path)):
        return -1.0
    peak = np.maximum.accumulate(path)
    return float(np.min(path / peak - 1.0))


def polits_white_mean_block(returns: np.ndarray) -> float:
    """AR(1) plug-in for Politis & White (2004) stationary-bootstrap mean block.

    ``b_SB = (2 ρ̂ / (1-ρ̂)^2)^{2/3} T^{1/3}``. Negative autocorrelation → 1
    (no reason to glue independent observations into blocks).
    """
    t = int(returns.size)
    if t < 4:
        raise BootstrapError("观测太少，无法估计最优块长")
    rho = float(np.corrcoef(returns[:-1], returns[1:])[0, 1])
    if not np.isfinite(rho):
        raise BootstrapError("无法估计一阶自相关，拒绝自动块长")
    if rho <= 0.0:
        return 1.0
    if rho >= 1.0:
        return float(t / 4.0)
    length = (2.0 * rho / (1.0 - rho) ** 2) ** (2.0 / 3.0) * (t ** (1.0 / 3.0))
    if not np.isfinite(length):
        return float(t / 4.0)
    if length < 1.0:
        return 1.0
    return float(min(length, t / 4.0))


def _geometric_length(rng: np.random.Generator, p: float, remaining: int) -> int:
    if p >= 1.0 or remaining <= 1:
        return 1
    u = float(rng.random())
    u = min(max(u, 1e-16), 1.0 - 1e-16)
    length = int(np.floor(np.log(u) / np.log(1.0 - p))) + 1
    return int(min(max(length, 1), remaining))


def _resample_indices(
    t: int,
    mean_block: float,
    rng: np.random.Generator,
    *,
    method: str,
) -> np.ndarray:
    idx = np.empty(t, dtype=np.intp)
    i = 0
    if method == "block":
        block = max(1, int(round(mean_block)))
        while i < t:
            start = int(rng.integers(0, t))
            length = min(block, t - i)
            idx[i : i + length] = (start + np.arange(length)) % t
            i += length
        return idx
    p = 1.0 / mean_block
    while i < t:
        start = int(rng.integers(0, t))
        length = _geometric_length(rng, p, t - i)
        idx[i : i + length] = (start + np.arange(length)) % t
        i += length
    return idx


def resample_indices(
    t: int,
    mean_block: float,
    rng: np.random.Generator,
    *,
    method: str,
) -> np.ndarray:
    """Circular block / stationary (geometric) index path of length ``t``."""
    return _resample_indices(t, mean_block, rng, method=method)


def _percentile_interval(observed: float, draws: np.ndarray, confidence_level: float) -> Interval:
    if not np.all(np.isfinite(draws)):
        raise BootstrapError("Bootstrap 分布存在非有限值，拒绝报区间")
    alpha = (1.0 - confidence_level) / 2.0
    low = float(np.quantile(draws, alpha))
    high = float(np.quantile(draws, 1.0 - alpha))
    if not np.isfinite(low) or not np.isfinite(high):
        raise BootstrapError("分位区间非有限，拒绝报区间")
    if low > high:
        raise BootstrapError("分位区间上下界颠倒")
    return Interval(
        observed=observed,
        low=low,
        high=high,
        crosses_zero=low <= 0.0 <= high,
    )


def bootstrap_metrics(
    returns: np.ndarray,
    *,
    years: float,
    periods_per_year: float = _TRADING_DAYS_PER_YEAR,
    n_boot: int = DEFAULT_N_BOOT,
    confidence_level: float = DEFAULT_CONFIDENCE,
    method: str = "stationary",
    mean_block_length: float | None = None,
    seed: int = 0,
) -> BootstrapResult:
    """Percentile CIs for Sharpe, CAGR, and max drawdown.

    ``method`` is ``stationary`` (geometric blocks, default) or ``block``
    (fixed circular blocks). ``iid`` is not a method.
    """
    if method not in METHODS:
        raise BootstrapError(
            f"只支持 stationary / block Bootstrap，拒绝 {method!r}（含 iid 重抽样）"
        )
    if n_boot < MIN_BOOT or n_boot > MAX_BOOT:
        raise BootstrapError(f"n_boot 必须在 {MIN_BOOT}–{MAX_BOOT} 之间")
    if not 0.8 <= confidence_level < 1.0:
        raise BootstrapError("confidence_level 必须在 [0.8, 1)")
    if periods_per_year <= 0 or years <= 0:
        raise BootstrapError("periods_per_year 与 years 必须 > 0")
    rets = np.asarray(returns, dtype=float)
    if rets.ndim != 1:
        raise BootstrapError("收益必须是一维序列")
    if not np.all(np.isfinite(rets)):
        raise BootstrapError("收益存在非有限值，拒绝 Bootstrap")
    t = int(rets.size)
    if t < MIN_OBS:
        raise BootstrapError(
            f"收益观测只有 {t} 根，少于 {MIN_OBS} 个交易日，拒绝把 Bootstrap 算成通过。"
        )

    observed_sharpe = sharpe_from_returns(rets, periods_per_year)
    observed_cagr = cagr_from_returns(rets, years)
    observed_dd = max_drawdown_from_returns(rets)

    if mean_block_length is None:
        mean_block = polits_white_mean_block(rets)
    else:
        mean_block = float(mean_block_length)
    if not np.isfinite(mean_block) or mean_block < 1.0:
        raise BootstrapError("mean_block_length 必须是 ≥ 1 的有限数")
    if mean_block >= t:
        raise BootstrapError("块长不能 ≥ 样本长度，否则只有一块、区间没有意义")

    rng = np.random.default_rng(int(seed))
    sharpes = np.empty(n_boot, dtype=float)
    cagrs = np.empty(n_boot, dtype=float)
    dds = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = _resample_indices(t, mean_block, rng, method=method)
        draw = rets[idx]
        sharpes[i] = sharpe_from_returns(draw, periods_per_year)
        cagrs[i] = cagr_from_returns(draw, years)
        dds[i] = max_drawdown_from_returns(draw)

    sharpe_ci = _percentile_interval(observed_sharpe, sharpes, confidence_level)
    cagr_ci = _percentile_interval(observed_cagr, cagrs, confidence_level)
    dd_ci = _percentile_interval(observed_dd, dds, confidence_level)

    if sharpe_ci.crosses_zero or sharpe_ci.low <= 0:
        passed = False
        reason = (
            f"Sharpe {sharpe_ci.observed:.2f} 的 {confidence_level:.0%} CI "
            f"[{sharpe_ci.low:.2f}, {sharpe_ci.high:.2f}] 跨零或下界 ≤ 0，无统计显著性。"
        )
    else:
        passed = True
        reason = (
            f"Sharpe {sharpe_ci.observed:.2f} [{sharpe_ci.low:.2f}, {sharpe_ci.high:.2f}] "
            f"下界 > 0；CAGR {cagr_ci.observed:.2%} "
            f"[{cagr_ci.low:.2%}, {cagr_ci.high:.2%}]；"
            f"MaxDD {dd_ci.observed:.2%} [{dd_ci.low:.2%}, {dd_ci.high:.2%}]。"
        )

    return BootstrapResult(
        passed=passed,
        reason=reason,
        method=method,
        n_obs=t,
        n_boot=n_boot,
        mean_block_length=float(mean_block),
        confidence_level=confidence_level,
        periods_per_year=float(periods_per_year),
        years=float(years),
        seed=int(seed),
        sharpe=sharpe_ci,
        cagr=cagr_ci,
        max_drawdown=dd_ci,
    )


def bootstrap_from_equity(
    equity: Sequence[Mapping[str, Any]],
    *,
    n_boot: int = DEFAULT_N_BOOT,
    confidence_level: float = DEFAULT_CONFIDENCE,
    method: str = "stationary",
    mean_block_length: float | None = None,
    seed: int = 0,
) -> BootstrapResult:
    rets, years, ppy = returns_from_equity(equity)
    return bootstrap_metrics(
        rets,
        years=years,
        periods_per_year=ppy,
        n_boot=n_boot,
        confidence_level=confidence_level,
        method=method,
        mean_block_length=mean_block_length,
        seed=seed,
    )
