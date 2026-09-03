"""White Reality Check (2000) and Hansen SPA (2005).

The universe is a T×K panel of performance differentials vs a benchmark
(default: 0, i.e. cash / no edge). Rows are dates, columns are trials.
Resampling is a *joint* stationary bootstrap so cross-trial dependence
is preserved. IID resampling is forbidden.

Hansen's SPA studentizes each column and recenters only the models that
are close to the null. White's RC is the unstudentized max mean. The
consistent SPA_c p-value gates VALIDATED: p ≥ α means we cannot claim
the best trial has edge after accounting for the search.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from quant.validation.bootstrap import polits_white_mean_block, resample_indices

MIN_OBS = 252
MIN_MODELS = 2
MAX_MODELS = 64
MIN_BOOT = 200
MAX_BOOT = 5_000
DEFAULT_N_BOOT = 1_000
DEFAULT_ALPHA = 0.05


class SpaError(ValueError):
    """Fail-loud Reality Check / SPA errors. Never invent a passing p-value."""


@dataclass(frozen=True)
class SpaModel:
    backtest_id: str | None
    mean: float
    t_stat: float
    omega: float
    is_best: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "backtest_id": self.backtest_id,
            "mean": self.mean,
            "t_stat": self.t_stat,
            "omega": self.omega,
            "is_best": self.is_best,
        }


@dataclass(frozen=True)
class SpaResult:
    passed: bool
    reason: str
    n_obs: int
    n_models: int
    n_boot: int
    alpha: float
    seed: int
    mean_block_length: float
    best_index: int
    statistic: float
    p_reality_check: float
    p_spa_lower: float
    p_spa_consistent: float
    p_spa_upper: float
    models: list[SpaModel]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "n_obs": self.n_obs,
            "n_models": self.n_models,
            "n_boot": self.n_boot,
            "alpha": self.alpha,
            "seed": self.seed,
            "mean_block_length": self.mean_block_length,
            "best_index": self.best_index,
            "statistic": self.statistic,
            "p_reality_check": self.p_reality_check,
            "p_spa_lower": self.p_spa_lower,
            "p_spa_consistent": self.p_spa_consistent,
            "p_spa_upper": self.p_spa_upper,
            "models": [item.to_dict() for item in self.models],
        }


def bartlett_long_run_variance(series: np.ndarray) -> float:
    """Bartlett HAC of the mean, lag = floor(T^{1/3})."""
    x = np.asarray(series, dtype=float)
    if x.ndim != 1:
        raise SpaError("HAC 需要一维序列")
    n = int(x.size)
    if n < 2:
        raise SpaError("序列太短，无法估计长期方差")
    centered = x - float(np.mean(x))
    gamma0 = float(np.dot(centered, centered) / n)
    lags = max(1, int(n ** (1.0 / 3.0)))
    var = gamma0
    for lag in range(1, lags + 1):
        gamma = float(np.dot(centered[lag:], centered[:-lag]) / n)
        weight = 1.0 - lag / (lags + 1.0)
        var += 2.0 * weight * gamma
    if not np.isfinite(var):
        raise SpaError("长期方差非有限")
    return float(max(var, 0.0))


def _omega(column: np.ndarray) -> float:
    var = bartlett_long_run_variance(column)
    omega = float(np.sqrt(var))
    mean = float(np.mean(column))
    if omega <= 1e-12:
        if abs(mean) <= 1e-15:
            return 0.0
        raise SpaError("非零常收益，SPA t 统计量没有定义")
    return omega


def _studentized(mean: float, omega: float, n: int) -> float:
    if omega <= 1e-12:
        return 0.0
    return float(np.sqrt(n) * mean / omega)


def _p_value(observed: float, draws: np.ndarray) -> float:
    if not np.all(np.isfinite(draws)):
        raise SpaError("Bootstrap 分布存在非有限值，拒绝报 p 值")
    return float(np.mean(draws >= observed))


def spa_test(
    differentials: np.ndarray,
    *,
    n_boot: int = DEFAULT_N_BOOT,
    alpha: float = DEFAULT_ALPHA,
    seed: int = 0,
    mean_block_length: float | None = None,
    ids: Sequence[str | None] | None = None,
) -> SpaResult:
    """White RC + Hansen SPA on a T×K panel of benchmark-relative returns."""
    diffs = np.asarray(differentials, dtype=float)
    if diffs.ndim != 2:
        raise SpaError("收益矩阵必须是二维 (T, K)")
    if not np.all(np.isfinite(diffs)):
        raise SpaError("收益存在非有限值，拒绝 SPA")
    n_obs, n_models = diffs.shape
    if n_models < MIN_MODELS:
        raise SpaError(f"跨策略 Reality Check 至少需要 {MIN_MODELS} 条试验，当前 {n_models}")
    if n_models > MAX_MODELS:
        raise SpaError(
            f"试验台账有 {n_models} 条，超过 {MAX_MODELS}。"
            "拒绝截断后再做多重检验。"
        )
    if n_obs < MIN_OBS:
        raise SpaError(
            f"共同交易日只有 {n_obs} 根，少于 {MIN_OBS}，拒绝把 SPA 算成通过。"
        )
    if n_boot < MIN_BOOT or n_boot > MAX_BOOT:
        raise SpaError(f"n_boot 必须在 {MIN_BOOT}–{MAX_BOOT} 之间")
    if not 0.01 <= alpha <= 0.2:
        raise SpaError("alpha 必须在 [0.01, 0.2]")
    if ids is not None and len(ids) != n_models:
        raise SpaError("模型 id 数量与列数不一致")

    finals = np.cumprod(1.0 + diffs, axis=0)[-1]
    if float(np.max(finals) - np.min(finals)) < 1e-8:
        raise SpaError("各试验净值无法区分，拒绝把重复试验算进多重检验")

    means = diffs.mean(axis=0)
    omegas = np.asarray([_omega(diffs[:, k]) for k in range(n_models)], dtype=float)
    t_stats = np.asarray(
        [_studentized(float(means[k]), float(omegas[k]), n_obs) for k in range(n_models)],
        dtype=float,
    )
    best = int(np.argmax(t_stats))
    statistic = float(max(float(np.max(t_stats)), 0.0))
    v_rc = float(np.max(np.sqrt(n_obs) * means))

    if mean_block_length is None:
        mean_block = polits_white_mean_block(diffs[:, best])
    else:
        mean_block = float(mean_block_length)
    if not np.isfinite(mean_block) or mean_block < 1.0:
        raise SpaError("mean_block_length 必须是 ≥ 1 的有限数")
    if mean_block >= n_obs:
        raise SpaError("块长不能 ≥ 样本长度")

    # Hansen (2005) threshold for the consistent recentering set.
    log_log = float(np.log(np.log(max(n_obs, 3))))
    if not np.isfinite(log_log) or log_log <= 0:
        raise SpaError("样本太短，无法计算 Hansen 的 log log 阈值")
    threshold = np.sqrt(2.0 * log_log) * omegas / np.sqrt(n_obs)
    mu_lower = np.maximum(means, 0.0)  # SPA_l: liberal (smaller p)
    mu_consistent = means * (means >= -threshold)
    mu_upper = means.copy()  # SPA_u: conservative (larger p)

    rng = np.random.default_rng(int(seed))
    rc_draws = np.empty(n_boot, dtype=float)
    spa_l = np.empty(n_boot, dtype=float)
    spa_c = np.empty(n_boot, dtype=float)
    spa_u = np.empty(n_boot, dtype=float)
    sqrt_n = float(np.sqrt(n_obs))
    for i in range(n_boot):
        idx = resample_indices(n_obs, mean_block, rng, method="stationary")
        boot_means = diffs[idx].mean(axis=0)
        rc_draws[i] = float(np.max(sqrt_n * (boot_means - means)))
        t_l = sqrt_n * (boot_means - mu_lower) / np.where(omegas > 1e-12, omegas, 1.0)
        t_c = sqrt_n * (boot_means - mu_consistent) / np.where(omegas > 1e-12, omegas, 1.0)
        t_u = sqrt_n * (boot_means - mu_upper) / np.where(omegas > 1e-12, omegas, 1.0)
        spa_l[i] = float(max(float(np.max(t_l)), 0.0))
        spa_c[i] = float(max(float(np.max(t_c)), 0.0))
        spa_u[i] = float(max(float(np.max(t_u)), 0.0))

    p_rc = _p_value(max(v_rc, 0.0), rc_draws) if v_rc > 0 else 1.0
    p_l = _p_value(statistic, spa_l)
    p_c = _p_value(statistic, spa_c)
    p_u = _p_value(statistic, spa_u)

    labels = list(ids) if ids is not None else [None] * n_models
    models = [
        SpaModel(
            backtest_id=labels[k],
            mean=float(means[k]),
            t_stat=float(t_stats[k]),
            omega=float(omegas[k]),
            is_best=k == best,
        )
        for k in range(n_models)
    ]

    passed = bool(p_c < alpha and statistic > 0)
    if statistic <= 0:
        reason = "所有试验相对基准的均值 ≤ 0，没有可检验的 edge。"
    elif passed:
        reason = (
            f"Hansen SPA_c p={p_c:.3f} < {alpha:.2f}，"
            f"在 {n_models} 条试验中拒绝「没有优于基准的模型」。"
            f" White RC p={p_rc:.3f}。"
        )
    else:
        reason = (
            f"Hansen SPA_c p={p_c:.3f} ≥ {alpha:.2f}，"
            f"不能声称这 {n_models} 条试验里最好的那个有 edge。"
            f" White RC p={p_rc:.3f}。不能进入 VALIDATED。"
        )

    return SpaResult(
        passed=passed,
        reason=reason,
        n_obs=n_obs,
        n_models=n_models,
        n_boot=n_boot,
        alpha=alpha,
        seed=int(seed),
        mean_block_length=float(mean_block),
        best_index=best,
        statistic=statistic,
        p_reality_check=p_rc,
        p_spa_lower=p_l,
        p_spa_consistent=p_c,
        p_spa_upper=p_u,
        models=models,
    )


def _date_key(value: object) -> str:
    if hasattr(value, "isoformat"):
        return str(value.isoformat())[:10]
    return str(value)[:10]


def returns_from_path(equity: Sequence[Mapping[str, Any]]) -> tuple[list[str], np.ndarray]:
    if len(equity) < 2:
        raise SpaError("净值不足 2 根，无法做 SPA")
    ordered = sorted(equity, key=lambda row: str(row["ts"]))
    dates: list[str] = []
    rets: list[float] = []
    prev = float(ordered[0]["strategy_value"])
    for point in ordered[1:]:
        current = float(point["strategy_value"])
        if prev == 0:
            raise SpaError("净值出现 0，拒绝计算 SPA")
        dates.append(_date_key(point["ts"]))
        rets.append(current / prev - 1.0)
        prev = current
    arr = np.asarray(rets, dtype=float)
    if not np.all(np.isfinite(arr)):
        raise SpaError("收益存在非有限值，拒绝 SPA")
    return dates, arr


def panel_from_equity_paths(
    paths: Sequence[tuple[str | None, Sequence[Mapping[str, Any]]]],
) -> tuple[np.ndarray, list[str | None]]:
    """Intersect dates across trial equity paths. Refuse to pad."""
    if len(paths) < MIN_MODELS:
        raise SpaError(f"跨策略 Reality Check 至少需要 {MIN_MODELS} 条试验，当前 {len(paths)}")
    parsed: list[tuple[str | None, dict[str, float]]] = []
    common: set[str] | None = None
    for ident, equity in paths:
        dates, rets = returns_from_path(equity)
        mapping = dict(zip(dates, rets.tolist()))
        parsed.append((ident, mapping))
        keys = set(mapping)
        common = keys if common is None else common & keys
    if not common:
        raise SpaError("各试验没有共同交易日，拒绝对齐")
    ordered = sorted(common)
    matrix = np.column_stack([[row[d] for d in ordered] for _ident, row in parsed])
    ids = [ident for ident, _row in parsed]
    return matrix, ids

