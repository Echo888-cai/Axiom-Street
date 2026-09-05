from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from quant.validation.walk_forward import (
    FoldObservation,
    WalkForwardError,
    WalkForwardFold,
    WalkForwardSpec,
    add_years,
    build_folds,
    score_walk_forward,
    slice_equity,
    stitch_oos_equity,
)


def _ts(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def _series(start: date, n_days: int, *, start_value: float, daily: float) -> list[dict]:
    """Weekday NAV with a small alternating shock so Sharpe std is non-zero."""
    points = []
    value = start_value
    day = start
    i = 0
    while len(points) < n_days:
        if day.weekday() < 5:
            shock = 0.004 if i % 2 == 0 else -0.003
            points.append({"ts": _ts(day), "strategy_value": value})
            value *= 1.0 + daily + shock
            i += 1
        day += timedelta(days=1)
    return points


def test_add_years_maps_feb29_to_feb28():
    assert add_years(date(2020, 2, 29), 1) == date(2021, 2, 28)
    assert add_years(date(2020, 2, 29), -1) == date(2019, 2, 28)


def test_rolling_folds_on_three_year_window():
    folds = build_folds(
        WalkForwardSpec(
            start=date(2018, 1, 1),
            end=date(2020, 12, 31),
            train_years=1,
            test_years=1,
            mode="rolling",
        )
    )
    assert len(folds) == 2
    assert folds[0].is_start == date(2018, 1, 1)
    assert folds[0].is_end == date(2018, 12, 31)
    assert folds[0].oos_start == date(2019, 1, 1)
    assert folds[0].oos_end == date(2019, 12, 31)
    assert folds[1].is_start == date(2019, 1, 1)
    assert folds[1].oos_start == date(2020, 1, 1)
    assert folds[1].oos_end == date(2020, 12, 31)


def test_anchored_folds_keep_is_origin():
    folds = build_folds(
        WalkForwardSpec(
            start=date(2018, 1, 1),
            end=date(2020, 12, 31),
            train_years=1,
            test_years=1,
            mode="anchored",
        )
    )
    assert len(folds) == 2
    assert folds[0].is_start == date(2018, 1, 1)
    assert folds[1].is_start == date(2018, 1, 1)
    assert folds[1].is_end == date(2019, 12, 31)
    assert folds[1].oos_start == date(2020, 1, 1)


def test_embargo_keeps_is_and_oos_from_overlapping():
    folds = build_folds(
        WalkForwardSpec(
            start=date(2018, 1, 1),
            end=date(2020, 12, 31),
            train_years=1,
            test_years=1,
            embargo_days=5,
        )
    )
    assert folds[0].is_end == date(2018, 12, 27)
    assert folds[0].oos_start == date(2019, 1, 1)
    assert folds[0].is_end < folds[0].oos_start


def test_train_three_years_on_golden_range_fails_loud():
    with pytest.raises(WalkForwardError, match="至少需要 2 折"):
        build_folds(
            WalkForwardSpec(
                start=date(2018, 1, 1),
                end=date(2020, 12, 31),
                train_years=3,
                test_years=1,
            )
        )


def test_truncated_stub_fold_is_dropped_then_fails_if_only_one_remains():
    with pytest.raises(WalkForwardError, match="至少需要 2 折"):
        build_folds(
            WalkForwardSpec(
                start=date(2018, 1, 1),
                end=date(2020, 2, 1),
                train_years=1,
                test_years=1,
            )
        )


def test_unknown_mode_fails_loud():
    with pytest.raises(WalkForwardError, match="rolling 或 anchored"):
        build_folds(
            WalkForwardSpec(
                start=date(2018, 1, 1),
                end=date(2020, 12, 31),
                train_years=1,
                test_years=1,
                mode="expanding",
            )
        )


def test_slice_and_stitch_compound_returns_not_levels():
    a = [
        {"ts": _ts(date(2019, 1, 2)), "strategy_value": 100.0},
        {"ts": _ts(date(2019, 1, 3)), "strategy_value": 110.0},
    ]
    b = [
        {"ts": _ts(date(2020, 1, 2)), "strategy_value": 50.0},
        {"ts": _ts(date(2020, 1, 3)), "strategy_value": 55.0},
    ]
    stitched = stitch_oos_equity([a, b])
    assert stitched[0]["strategy_value"] == pytest.approx(1.0)
    assert stitched[1]["strategy_value"] == pytest.approx(1.1)
    assert stitched[2]["strategy_value"] == pytest.approx(1.21)
    sliced = slice_equity(a + b, date(2020, 1, 1), date(2020, 1, 31))
    assert [p["strategy_value"] for p in sliced] == [50.0, 55.0]


def _fold(index: int, year_is: int, year_oos: int) -> WalkForwardFold:
    return WalkForwardFold(
        index=index,
        is_start=date(year_is, 1, 1),
        is_end=date(year_is, 12, 31),
        oos_start=date(year_oos, 1, 1),
        oos_end=date(year_oos, 12, 31),
    )


def test_score_passes_weak_consistent_edge():
    # Small positive drift both IS and OOS — 200DMA-like, not a collapse.
    obs = []
    for i, (is_year, oos_year) in enumerate(((2018, 2019), (2019, 2020))):
        is_eq = _series(date(is_year, 1, 2), 80, start_value=100_000, daily=0.0003)
        oos_eq = _series(date(oos_year, 1, 2), 80, start_value=110_000, daily=0.0003)
        obs.append(
            FoldObservation(fold=_fold(i, is_year, oos_year), is_equity=is_eq, oos_equity=oos_eq)
        )
    score = score_walk_forward(obs)
    assert score.n_folds == 2
    assert score.overfit_collapse is False
    assert score.passed is True
    assert score.combined_oos_bars >= 60
    assert score.combined_oos_sharpe > 0


def test_score_fails_is_strong_oos_negative():
    obs = []
    for i, (is_year, oos_year) in enumerate(((2018, 2019), (2019, 2020))):
        is_eq = _series(date(is_year, 1, 2), 80, start_value=100_000, daily=0.003)
        oos_eq = _series(date(oos_year, 1, 2), 80, start_value=200_000, daily=-0.002)
        obs.append(
            FoldObservation(fold=_fold(i, is_year, oos_year), is_equity=is_eq, oos_equity=oos_eq)
        )
    score = score_walk_forward(obs)
    assert score.mean_is_sharpe > 0.5
    assert score.combined_oos_sharpe < 0
    assert score.overfit_collapse is True
    assert score.passed is False


def test_score_fails_loud_when_oos_bars_missing():
    fold = _fold(0, 2018, 2019)
    short = _series(date(2019, 1, 2), 5, start_value=100_000, daily=0.001)
    long = _series(date(2018, 1, 2), 80, start_value=100_000, daily=0.001)
    with pytest.raises(WalkForwardError, match="样本外只有"):
        score_walk_forward(
            [
                FoldObservation(fold=fold, is_equity=long, oos_equity=short),
                FoldObservation(fold=_fold(1, 2019, 2020), is_equity=long, oos_equity=long),
            ]
        )
