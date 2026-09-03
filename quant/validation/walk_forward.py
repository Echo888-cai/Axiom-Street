"""Walk-forward folds and OOS scoring.

One engine run covers ``[is_start, oos_end]`` so indicators have warmup.
Scoring uses the **concatenated OOS daily returns**, not the mean of fold
Sharpes. A classic collapse (strong IS, negative combined OOS) fails the gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any, Mapping, Sequence

from quant.metrics.performance import compute_metrics_from_equity

MIN_FOLDS = 2
MIN_OOS_CALENDAR_DAYS = 60
MIN_OOS_BARS_PER_FOLD = 20
MIN_COMBINED_OOS_BARS = 60
IS_LOOKS_SKILLED = 0.5
MODES = frozenset({"rolling", "anchored"})


class WalkForwardError(ValueError):
    """Fail-loud walk-forward construction or scoring error."""


@dataclass(frozen=True)
class WalkForwardSpec:
    start: date
    end: date
    train_years: int
    test_years: int
    mode: str = "rolling"
    embargo_days: int = 1


@dataclass(frozen=True)
class WalkForwardFold:
    index: int
    is_start: date
    is_end: date
    oos_start: date
    oos_end: date

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "is_start": self.is_start.isoformat(),
            "is_end": self.is_end.isoformat(),
            "oos_start": self.oos_start.isoformat(),
            "oos_end": self.oos_end.isoformat(),
        }


@dataclass(frozen=True)
class FoldObservation:
    fold: WalkForwardFold
    is_equity: list[dict[str, Any]]
    oos_equity: list[dict[str, Any]]


@dataclass(frozen=True)
class WalkForwardScore:
    passed: bool
    overfit_collapse: bool
    reason: str
    n_folds: int
    mean_is_sharpe: float
    mean_oos_sharpe: float
    combined_oos_sharpe: float
    combined_oos_bars: int
    folds: list[dict[str, Any]]
    oos_equity: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "overfit_collapse": self.overfit_collapse,
            "reason": self.reason,
            "n_folds": self.n_folds,
            "mean_is_sharpe": self.mean_is_sharpe,
            "mean_oos_sharpe": self.mean_oos_sharpe,
            "combined_oos_sharpe": self.combined_oos_sharpe,
            "combined_oos_bars": self.combined_oos_bars,
            "folds": self.folds,
            "oos_equity": self.oos_equity,
        }


def add_years(value: date, years: int) -> date:
    """Shift a date by calendar years. Feb 29 maps to Feb 28 in non-leap years."""
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def point_date(ts: Any) -> date:
    if isinstance(ts, datetime):
        return ts.date()
    if isinstance(ts, date):
        return ts
    if hasattr(ts, "date") and callable(ts.date):
        resolved = ts.date()
        if isinstance(resolved, date):
            return resolved
    text = str(ts).strip()
    if not text:
        raise WalkForwardError("净值点缺少时间戳")
    return date.fromisoformat(text[:10])


def slice_equity(
    equity: Sequence[Mapping[str, Any]], start: date, end: date
) -> list[dict[str, Any]]:
    if end < start:
        raise WalkForwardError("切片结束日早于开始日")
    out: list[dict[str, Any]] = []
    for point in equity:
        ts = point.get("ts")
        if ts is None:
            raise WalkForwardError("净值点缺少 ts")
        day = point_date(ts)
        if start <= day <= end:
            out.append(dict(point))
    return out


def stitch_oos_equity(segments: Sequence[Sequence[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    """Compound OOS fold returns onto a unit-starting curve.

    Levels are not concatenated — fold 2 does not resume fold 1's dollar NAV.
    """
    out: list[dict[str, Any]] = []
    value = 1.0
    peak = 1.0
    origin_written = False
    for segment in segments:
        rows = list(segment)
        if len(rows) < 2:
            continue
        prev = float(rows[0]["strategy_value"])
        if not origin_written:
            out.append(
                {
                    "ts": rows[0]["ts"],
                    "strategy_value": 1.0,
                    "benchmark_value": None,
                    "drawdown": 0.0,
                }
            )
            origin_written = True
        for point in rows[1:]:
            current = float(point["strategy_value"])
            if prev == 0:
                raise WalkForwardError("净值出现 0，拒绝拼接样本外曲线")
            value *= current / prev
            peak = max(peak, value)
            out.append(
                {
                    "ts": point["ts"],
                    "strategy_value": value,
                    "benchmark_value": None,
                    "drawdown": value / peak - 1.0,
                }
            )
            prev = current
    return out


def build_folds(spec: WalkForwardSpec) -> list[WalkForwardFold]:
    if spec.train_years < 1:
        raise WalkForwardError("train_years 必须 >= 1")
    if spec.test_years < 1:
        raise WalkForwardError("test_years 必须 >= 1")
    mode = spec.mode.strip().lower()
    if mode not in MODES:
        raise WalkForwardError("mode 只能是 rolling 或 anchored")
    if spec.embargo_days < 1:
        raise WalkForwardError("embargo_days 必须 >= 1，样本内与样本外不能重叠")
    if spec.end <= spec.start:
        raise WalkForwardError("结束日期必须晚于开始日期")

    folds: list[WalkForwardFold] = []
    oos_start = add_years(spec.start, spec.train_years)
    index = 0
    while oos_start <= spec.end:
        oos_end = add_years(oos_start, spec.test_years) - timedelta(days=1)
        if oos_end > spec.end:
            oos_end = spec.end
        calendar_days = (oos_end - oos_start).days + 1
        if calendar_days < MIN_OOS_CALENDAR_DAYS:
            break
        if mode == "anchored":
            is_start = spec.start
        else:
            is_start = add_years(oos_start, -spec.train_years)
            if is_start < spec.start:
                is_start = spec.start
        is_end = oos_start - timedelta(days=spec.embargo_days)
        if is_end < is_start:
            raise WalkForwardError("embargo 把样本内窗口吃空了，请减小 embargo_days")
        folds.append(
            WalkForwardFold(
                index=index,
                is_start=is_start,
                is_end=is_end,
                oos_start=oos_start,
                oos_end=oos_end,
            )
        )
        index += 1
        oos_start = add_years(oos_start, spec.test_years)
    if len(folds) < MIN_FOLDS:
        raise WalkForwardError(
            f"只能切出 {len(folds)} 个完整样本外折。Walk-forward 至少需要 {MIN_FOLDS} 折。"
            "请缩短训练年数、缩短测试年数，或拉长历史区间。"
        )
    return folds


def _sharpe_and_bars(equity: Sequence[Mapping[str, Any]]) -> tuple[float, int]:
    rows = [dict(p) for p in equity]
    bars = len(rows)
    if bars < 2:
        return 0.0, bars
    metrics = compute_metrics_from_equity(rows)
    sharpe = metrics.get("sharpe")
    return (float(sharpe) if sharpe is not None else 0.0), bars


def score_walk_forward(observations: Sequence[FoldObservation]) -> WalkForwardScore:
    if len(observations) < MIN_FOLDS:
        raise WalkForwardError(
            f"Walk-forward 至少需要 {MIN_FOLDS} 折完整结果，实际 {len(observations)}"
        )
    fold_rows: list[dict[str, Any]] = []
    is_sharpes: list[float] = []
    oos_sharpes: list[float] = []
    oos_segments: list[list[dict[str, Any]]] = []
    for obs in observations:
        is_sharpe, is_bars = _sharpe_and_bars(obs.is_equity)
        oos_sharpe, oos_bars = _sharpe_and_bars(obs.oos_equity)
        if is_bars < 2:
            raise WalkForwardError(f"第 {obs.fold.index + 1} 折样本内净值不足 2 根 K 线")
        if oos_bars < MIN_OOS_BARS_PER_FOLD:
            raise WalkForwardError(
                f"第 {obs.fold.index + 1} 折样本外只有 {oos_bars} 根 K 线，"
                f"少于 {MIN_OOS_BARS_PER_FOLD}"
            )
        is_sharpes.append(is_sharpe)
        oos_sharpes.append(oos_sharpe)
        oos_segments.append([dict(p) for p in obs.oos_equity])
        row = obs.fold.to_dict()
        row.update(
            {
                "is_sharpe": is_sharpe,
                "oos_sharpe": oos_sharpe,
                "is_bars": is_bars,
                "oos_bars": oos_bars,
            }
        )
        fold_rows.append(row)

    stitched = stitch_oos_equity(oos_segments)
    combined_sharpe, combined_points = _sharpe_and_bars(stitched)
    combined_bars = max(combined_points - 1, 0)
    if combined_bars < MIN_COMBINED_OOS_BARS:
        raise WalkForwardError(
            f"拼接样本外只有 {combined_bars} 个收益观测，少于 {MIN_COMBINED_OOS_BARS}"
        )

    mean_is = float(mean(is_sharpes))
    mean_oos = float(mean(oos_sharpes))
    collapse = mean_is > IS_LOOKS_SKILLED and combined_sharpe < 0
    passed = not collapse
    if collapse:
        reason = (
            f"样本内 Sharpe 均值 {mean_is:.2f} > {IS_LOOKS_SKILLED}，"
            f"但拼接样本外 Sharpe {combined_sharpe:.2f} < 0，判定为过拟合塌缩。"
        )
    else:
        reason = (
            f"Walk-forward 通过：{len(observations)} 折拼接样本外 Sharpe "
            f"{combined_sharpe:.2f}，未见样本内好看、样本外翻脸。"
        )
    return WalkForwardScore(
        passed=passed,
        overfit_collapse=collapse,
        reason=reason,
        n_folds=len(observations),
        mean_is_sharpe=mean_is,
        mean_oos_sharpe=mean_oos,
        combined_oos_sharpe=combined_sharpe,
        combined_oos_bars=combined_bars,
        folds=fold_rows,
        oos_equity=_json_equity(stitched),
    )


def _json_equity(points: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for point in points:
        ts = point["ts"]
        if hasattr(ts, "isoformat"):
            ts_text = ts.isoformat()
        else:
            ts_text = str(ts)
        out.append(
            {
                "ts": ts_text,
                "strategy_value": float(point["strategy_value"]),
                "benchmark_value": point.get("benchmark_value"),
                "drawdown": point.get("drawdown"),
            }
        )
    return out
