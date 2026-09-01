from datetime import datetime, timezone

import pandas as pd

from quant.data.quality import validate_ohlcv


def _frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _bar(day: int, **kwargs) -> dict:
    row = {
        "timestamp": datetime(2020, 1, day, tzinfo=timezone.utc),
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 1_000,
        "dividends": 0.0,
        "stock_splits": 0.0,
    }
    row.update(kwargs)
    return row


def test_empty_frame_is_blocking():
    report = validate_ohlcv(_frame([]))
    assert report.has_blocking_issues
    assert report.issues[0].rule == "empty"


def test_clean_frame_passes():
    report = validate_ohlcv(_frame([_bar(2), _bar(3), _bar(6), _bar(7), _bar(8)]))
    assert not report.has_blocking_issues


def test_duplicate_timestamps_blocking():
    report = validate_ohlcv(_frame([_bar(2), _bar(2), _bar(3)]))
    assert any(i.rule == "duplicate_timestamps" and i.severity == "blocking" for i in report.issues)


def test_monotonic_dates_blocking():
    report = validate_ohlcv(_frame([_bar(5), _bar(2), _bar(3)]))
    assert any(i.rule == "monotonic_dates" and i.severity == "blocking" for i in report.issues)


def test_ohlc_high_below_close_blocking():
    report = validate_ohlcv(_frame([_bar(2, high=100.0, close=100.5)]))
    assert any(i.rule == "ohlc_consistency" for i in report.issues)


def test_ohlc_low_above_open_blocking():
    report = validate_ohlcv(_frame([_bar(2, low=100.5, open=100.0)]))
    assert any(i.rule == "ohlc_consistency" for i in report.issues)


def test_non_positive_prices_blocking():
    report = validate_ohlcv(_frame([_bar(2, close=0.0)]))
    assert any(i.rule == "non_positive_prices" for i in report.issues)


def test_price_jump_without_split_blocking():
    report = validate_ohlcv(_frame([_bar(2, close=100.0), _bar(3, close=160.0)]))
    assert any(i.rule == "price_jumps" for i in report.issues)


def test_price_jump_with_split_ok():
    report = validate_ohlcv(
        _frame(
            [_bar(2, close=100.0), _bar(3, close=50.0, stock_splits=0.5, high=51, low=49, open=50)]
        )
    )
    assert not any(i.rule == "price_jumps" for i in report.issues)


def test_calendar_gap_blocking():
    report = validate_ohlcv(_frame([_bar(2), _bar(20)]))
    assert any(i.rule == "trading_day_gaps" for i in report.issues)


def test_zero_volume_is_warning_not_blocking():
    report = validate_ohlcv(_frame([_bar(2, volume=0), _bar(3), _bar(6)]))
    warnings = [i for i in report.issues if i.rule == "zero_volume"]
    assert warnings
    assert warnings[0].severity == "warning"
    assert not report.has_blocking_issues or not any(
        i.rule == "zero_volume" and i.severity == "blocking" for i in report.issues
    )


def test_stale_data_warning_when_no_expected_end():
    report = validate_ohlcv(
        _frame([_bar(2), _bar(3)]),
        as_of=datetime(2020, 3, 1, tzinfo=timezone.utc),
    )
    assert any(i.rule == "stale_data" and i.severity == "warning" for i in report.issues)


def test_stale_skipped_when_expected_end_set():
    report = validate_ohlcv(
        _frame([_bar(2), _bar(3)]),
        as_of=datetime(2020, 3, 1, tzinfo=timezone.utc),
        expected_end=datetime(2020, 1, 3, tzinfo=timezone.utc),
    )
    assert not any(i.rule == "stale_data" for i in report.issues)


def test_report_to_dict_includes_blocking_flag():
    report = validate_ohlcv(_frame([]))
    payload = report.to_dict()
    assert payload["has_blocking_issues"] is True
    assert payload["row_count"] == 0
