"""Regime stability: slice strategy returns by market state.

Bull/bear is a 20% peak-to-trough on the *benchmark* path (not the
strategy). A bear starts the day drawdown from the running peak is
≤ −20% and ends the day the benchmark makes a new high.

High/low vol is 21-day realized volatility of the benchmark versus the
sample median of that series. Constant vol cannot be split — fail loud.

Rate cycles are FOMC-dated hiking/cutting windows (historical facts, not
a live feed). Hold is everything in between and is reported, not gated.

Stress windows (2008 GFC, 2020-03, 2022 hiking bear) are calendar facts.
They are reported when in-sample; they do not gate VALIDATED.

Sharpe uses the same definition as the rest of Axiom (annualized from the
slice). All-zero returns (cash) are Sharpe = 0, not undefined. A
complementary regime that is strictly negative while another is strictly
positive is a collapse and fails the gate. Concentration with zeros is
annotated, not failed — that is the 200DMA-in-cash case.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence

import numpy as np

_TRADING_DAYS_PER_YEAR = 252.0
BEAR_DRAWDOWN = -0.20
VOL_WINDOW = 21
MIN_AXIS_OBS = 60
MIN_STRESS_OBS = 10

# Inclusive [start, end]. Source: FOMC target-rate change effective dates.
RATE_SPANS: tuple[tuple[date, date, str], ...] = (
    (date(2001, 1, 3), date(2003, 6, 25), "cut"),
    (date(2004, 6, 30), date(2006, 6, 29), "hike"),
    (date(2007, 9, 18), date(2008, 12, 16), "cut"),
    (date(2015, 12, 16), date(2018, 12, 19), "hike"),
    (date(2019, 7, 31), date(2020, 3, 15), "cut"),
    (date(2022, 3, 16), date(2023, 7, 26), "hike"),
    (date(2024, 9, 18), date(9999, 12, 31), "cut"),
)

STRESS_WINDOWS: tuple[tuple[str, date, date, str], ...] = (
    ("gfc_2008", date(2008, 9, 2), date(2009, 3, 9), "2008 金融危机（雷曼至低点）"),
    ("covid_2020_03", date(2020, 2, 19), date(2020, 3, 23), "2020-03 COVID 急跌"),
    ("hiking_bear_2022", date(2022, 1, 3), date(2022, 10, 12), "2022 加息熊市"),
)

SLICE_LABELS = {
    "bull": "牛市",
    "bear": "熊市",
    "high_vol": "高波动",
    "low_vol": "低波动",
    "hike": "加息",
    "cut": "降息",
    "hold": "利率持有",
}


class RegimeError(ValueError):
    """Fail-loud regime errors. Never invent a passing slice."""


@dataclass(frozen=True)
class RegimeSlice:
    key: str
    axis: str
    label: str
    n_obs: int
    sharpe: float | None
    win_rate: float | None
    covered: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "axis": self.axis,
            "label": self.label,
            "n_obs": self.n_obs,
            "sharpe": self.sharpe,
            "win_rate": self.win_rate,
            "covered": self.covered,
        }


@dataclass(frozen=True)
class RegimeResult:
    passed: bool
    reason: str
    single_regime: bool
    concentrated_in: str | None
    n_obs: int
    periods_per_year: float
    bear_drawdown: float
    vol_window: int
    min_axis_obs: int
    slices: list[RegimeSlice]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "single_regime": self.single_regime,
            "concentrated_in": self.concentrated_in,
            "n_obs": self.n_obs,
            "periods_per_year": self.periods_per_year,
            "bear_drawdown": self.bear_drawdown,
            "vol_window": self.vol_window,
            "min_axis_obs": self.min_axis_obs,
            "slices": [item.to_dict() for item in self.slices],
        }


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _as_date(value: datetime) -> date:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).date()
    return value.date()


def rate_regime(day: date) -> str:
    for start, end, kind in RATE_SPANS:
        if start <= day <= end:
            return kind
    return "hold"


def in_stress_window(day: date, start: date, end: date) -> bool:
    return start <= day <= end


def label_bull_bear(
    benchmark_levels: np.ndarray, *, threshold: float = BEAR_DRAWDOWN
) -> np.ndarray:
    """Return-aligned labels: length n-1 for n benchmark levels.

    Label i is the state at level i+1 (the close that realizes return i).
    """
    if threshold >= 0:
        raise RegimeError("熊市回撤阈值必须 < 0")
    levels = np.asarray(benchmark_levels, dtype=float)
    if levels.size < 2:
        raise RegimeError("基准净值不足 2 根，无法划分牛/熊")
    if not np.all(np.isfinite(levels)):
        raise RegimeError("基准净值存在非有限值，拒绝划分牛/熊")
    if np.any(levels <= 0):
        raise RegimeError("基准净值必须 > 0")

    n = int(levels.size) - 1
    labels = np.empty(n, dtype=object)
    peak = float(levels[0])
    state = "bull"
    for i in range(1, int(levels.size)):
        price = float(levels[i])
        if price > peak:
            peak = price
            state = "bull"
        drawdown = price / peak - 1.0
        if drawdown <= threshold + 1e-12:
            state = "bear"
        labels[i - 1] = state
    return labels


def label_vol(
    benchmark_returns: np.ndarray,
    *,
    window: int = VOL_WINDOW,
) -> np.ndarray:
    """High/low vs sample median of trailing realized vol. Unclassified → ''."""
    rets = np.asarray(benchmark_returns, dtype=float)
    if rets.ndim != 1:
        raise RegimeError("基准收益必须是一维序列")
    if window < 5:
        raise RegimeError("波动窗口必须 ≥ 5")
    t = int(rets.size)
    labels = np.full(t, "", dtype=object)
    if t < window:
        return labels
    vol = np.empty(t - window + 1, dtype=float)
    for i in range(vol.size):
        sl = rets[i : i + window]
        std = float(np.std(sl, ddof=1))
        if not np.isfinite(std):
            raise RegimeError("基准实现波动非有限，拒绝划分高/低波动")
        vol[i] = std
    median = float(np.median(vol))
    if not np.isfinite(median):
        raise RegimeError("无法计算波动中位数")
    # Align the window's vol to the last day of the window.
    for i, value in enumerate(vol):
        labels[i + window - 1] = "high_vol" if value > median else "low_vol"
    return labels


def label_rate(dates: Sequence[date]) -> np.ndarray:
    return np.asarray([rate_regime(day) for day in dates], dtype=object)


def sharpe_from_slice(returns: np.ndarray, periods_per_year: float) -> float:
    if len(returns) < 2:
        raise RegimeError("收益长度不足以计算 Sharpe")
    if not np.all(np.isfinite(returns)):
        raise RegimeError("收益存在非有限值，拒绝计算制度 Sharpe")
    if np.allclose(returns, 0.0):
        return 0.0
    std = float(np.std(returns, ddof=1))
    if not np.isfinite(std) or std <= 1e-12:
        raise RegimeError("非零常收益，Sharpe 没有定义")
    return float(np.mean(returns) / std * np.sqrt(periods_per_year))


def win_rate_from_slice(returns: np.ndarray) -> float:
    if len(returns) < 1:
        raise RegimeError("收益为空，无法计算胜率")
    return float(np.mean(returns > 0.0))


def _periods_per_year(timestamps: Sequence[datetime]) -> float:
    if len(timestamps) < 2:
        raise RegimeError("净值不足 2 根，无法判断采样频率")
    deltas = np.diff([ts.timestamp() for ts in timestamps]) / 86400.0
    median = float(np.median(deltas)) if len(deltas) else 1.0
    if 0.4 <= median <= 2.0:
        return _TRADING_DAYS_PER_YEAR
    if 4.0 <= median <= 10.0:
        return 52.0
    if 20.0 <= median <= 45.0:
        return 12.0
    raise RegimeError(f"净值采样不是日/周/月频（中位间隔 {median:.2f} 天），拒绝制度划分")


def series_from_equity(
    equity: Sequence[Mapping[str, Any]],
) -> tuple[np.ndarray, np.ndarray, list[date], float]:
    """Strategy returns, benchmark returns, return-end dates, periods/year."""
    if len(equity) < 2:
        raise RegimeError("净值不足 2 根，无法做制度划分")
    ordered = sorted(equity, key=lambda row: _as_datetime(row["ts"]))
    strategy = np.asarray([float(row["strategy_value"]) for row in ordered], dtype=float)
    if any("benchmark_value" not in row or row["benchmark_value"] is None for row in ordered):
        raise RegimeError("缺少基准净值，拒绝用策略自身曲线冒充市场状态")
    benchmark = np.asarray([float(row["benchmark_value"]) for row in ordered], dtype=float)
    if not np.all(np.isfinite(strategy)) or not np.all(np.isfinite(benchmark)):
        raise RegimeError("净值存在非有限值，拒绝制度划分")
    if np.any(strategy == 0) or np.any(benchmark <= 0):
        raise RegimeError("净值出现 0 或非正基准，拒绝计算收益")
    strat_rets = strategy[1:] / strategy[:-1] - 1.0
    bench_rets = benchmark[1:] / benchmark[:-1] - 1.0
    if not np.all(np.isfinite(strat_rets)) or not np.all(np.isfinite(bench_rets)):
        raise RegimeError("收益存在非有限值，拒绝制度划分")
    stamps = [_as_datetime(row["ts"]) for row in ordered]
    ppy = _periods_per_year(stamps)
    dates = [_as_date(ts) for ts in stamps[1:]]
    return strat_rets, bench_rets, dates, ppy


def _slice_label(key: str) -> str:
    if key in SLICE_LABELS:
        return SLICE_LABELS[key]
    for sid, _start, _end, title in STRESS_WINDOWS:
        if key == sid:
            return title
    return key


def _metrics(
    returns: np.ndarray,
    mask: np.ndarray,
    *,
    key: str,
    axis: str,
    ppy: float,
    min_obs: int,
) -> RegimeSlice:
    n = int(np.sum(mask))
    label = _slice_label(key)
    if n == 0:
        return RegimeSlice(
            key=key, axis=axis, label=label, n_obs=0, sharpe=None, win_rate=None, covered=False
        )
    if n < min_obs:
        return RegimeSlice(
            key=key, axis=axis, label=label, n_obs=n, sharpe=None, win_rate=None, covered=False
        )
    sl = returns[mask]
    return RegimeSlice(
        key=key,
        axis=axis,
        label=label,
        n_obs=n,
        sharpe=sharpe_from_slice(sl, ppy),
        win_rate=win_rate_from_slice(sl),
        covered=True,
    )


def _pair_verdict(left: RegimeSlice, right: RegimeSlice, *, need_both: str) -> str | None:
    if not left.covered or not right.covered:
        return (
            f"样本未同时覆盖{left.label}与{right.label}"
            f"（各需至少 {MIN_AXIS_OBS} 个交易日），{need_both}"
        )
    assert left.sharpe is not None and right.sharpe is not None
    if left.sharpe > 0 and right.sharpe < 0:
        return f"只在{left.label}有效，{right.label} Sharpe 为负"
    if right.sharpe > 0 and left.sharpe < 0:
        return f"只在{right.label}有效，{left.label} Sharpe 为负"
    if left.sharpe <= 0 and right.sharpe <= 0:
        return f"{left.label}/{right.label} Sharpe 均未为正"
    return None


def _concentration(*slices: RegimeSlice) -> tuple[bool, str | None]:
    positive = [
        item for item in slices if item.covered and item.sharpe is not None and item.sharpe > 0
    ]
    if len(positive) == 1:
        return True, positive[0].key
    return False, None


def score_regime(
    equity: Sequence[Mapping[str, Any]],
    *,
    bear_drawdown: float = BEAR_DRAWDOWN,
    vol_window: int = VOL_WINDOW,
    min_axis_obs: int = MIN_AXIS_OBS,
    min_stress_obs: int = MIN_STRESS_OBS,
) -> RegimeResult:
    strat, bench, dates, ppy = series_from_equity(equity)
    ordered = sorted(equity, key=lambda row: _as_datetime(row["ts"]))
    levels = np.asarray([float(row["benchmark_value"]) for row in ordered], dtype=float)
    trend = label_bull_bear(levels, threshold=bear_drawdown)
    vol = label_vol(bench, window=vol_window)
    rate = label_rate(dates)

    slices = [
        _metrics(strat, trend == "bull", key="bull", axis="trend", ppy=ppy, min_obs=min_axis_obs),
        _metrics(strat, trend == "bear", key="bear", axis="trend", ppy=ppy, min_obs=min_axis_obs),
        _metrics(
            strat, vol == "high_vol", key="high_vol", axis="vol", ppy=ppy, min_obs=min_axis_obs
        ),
        _metrics(strat, vol == "low_vol", key="low_vol", axis="vol", ppy=ppy, min_obs=min_axis_obs),
        _metrics(strat, rate == "hike", key="hike", axis="rate", ppy=ppy, min_obs=min_axis_obs),
        _metrics(strat, rate == "cut", key="cut", axis="rate", ppy=ppy, min_obs=min_axis_obs),
        _metrics(strat, rate == "hold", key="hold", axis="rate", ppy=ppy, min_obs=min_axis_obs),
    ]
    by_key = {item.key: item for item in slices}
    for sid, start, end, _title in STRESS_WINDOWS:
        mask = np.asarray([in_stress_window(day, start, end) for day in dates])
        slices.append(
            _metrics(strat, mask, key=sid, axis="stress", ppy=ppy, min_obs=min_stress_obs)
        )

    failures: list[str] = []
    trend_fail = _pair_verdict(by_key["bull"], by_key["bear"], need_both="无法判定趋势稳定性")
    if trend_fail:
        failures.append(trend_fail)
    vol_fail = _pair_verdict(by_key["high_vol"], by_key["low_vol"], need_both="无法判定波动稳定性")
    if vol_fail:
        failures.append(vol_fail)
    rate_fail = _pair_verdict(by_key["hike"], by_key["cut"], need_both="无法判定利率周期稳定性")
    if rate_fail:
        failures.append(rate_fail)

    single_trend, conc_trend = _concentration(by_key["bull"], by_key["bear"])
    single_vol, conc_vol = _concentration(by_key["high_vol"], by_key["low_vol"])
    single_rate, conc_rate = _concentration(by_key["hike"], by_key["cut"])
    single = single_trend or single_vol or single_rate
    concentrated_in = conc_trend or conc_vol or conc_rate

    if failures:
        passed = False
        reason = "；".join(failures) + "。不能进入 VALIDATED。"
    elif single:
        passed = True
        label = SLICE_LABELS.get(concentrated_in or "", concentrated_in or "")
        reason = (
            f"互补制度 Sharpe ≥ 0，但 edge 集中在{label}。"
            f"牛 {by_key['bull'].sharpe:.2f} / 熊 {by_key['bear'].sharpe:.2f}；"
            f"高波动 {by_key['high_vol'].sharpe:.2f} / 低波动 {by_key['low_vol'].sharpe:.2f}；"
            f"加息 {by_key['hike'].sharpe:.2f} / 降息 {by_key['cut'].sharpe:.2f}。"
        )
    else:
        passed = True
        reason = (
            f"牛/熊、高/低波动、加息/降息均未塌缩。"
            f"牛 {by_key['bull'].sharpe:.2f} / 熊 {by_key['bear'].sharpe:.2f}；"
            f"高波动 {by_key['high_vol'].sharpe:.2f} / 低波动 {by_key['low_vol'].sharpe:.2f}；"
            f"加息 {by_key['hike'].sharpe:.2f} / 降息 {by_key['cut'].sharpe:.2f}。"
        )

    return RegimeResult(
        passed=passed,
        reason=reason,
        single_regime=single and passed,
        concentrated_in=concentrated_in if (single and passed) else None,
        n_obs=int(strat.size),
        periods_per_year=float(ppy),
        bear_drawdown=float(bear_drawdown),
        vol_window=int(vol_window),
        min_axis_obs=int(min_axis_obs),
        slices=slices,
    )
