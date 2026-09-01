from datetime import datetime, timezone

import pandas as pd

from quant.data.lean_converter import bars_to_lean_daily_csv, build_factor_file


def test_bars_to_lean_daily_csv_deci_cents():
    df = pd.DataFrame(
        [
            {
                "timestamp": datetime(2020, 1, 2, tzinfo=timezone.utc),
                "open": 100.0,
                "high": 101.0,
                "low": 99.5,
                "close": 100.5,
                "volume": 1_000_000,
            }
        ]
    )
    csv = bars_to_lean_daily_csv(df)
    assert "20200101" in csv or "20200102" in csv
    assert "1005000" in csv  # 100.5 * 10000
    assert "1000000" in csv


def test_factor_file_includes_dividend_event():
    df = pd.DataFrame(
        [
            {
                "timestamp": datetime(2020, 1, 2, tzinfo=timezone.utc),
                "open": 100,
                "high": 100,
                "low": 100,
                "close": 100,
                "volume": 1,
                "dividends": 1.0,
                "stock_splits": 0.0,
            },
            {
                "timestamp": datetime(2020, 2, 3, tzinfo=timezone.utc),
                "open": 100,
                "high": 100,
                "low": 100,
                "close": 100,
                "volume": 1,
                "dividends": 0.0,
                "stock_splits": 2.0,
            },
        ]
    )
    text = build_factor_file(df)
    assert "20501231,1,1,0" in text
    assert "20200101" in text or "20200102" in text
    assert "20200202" in text or "20200203" in text
