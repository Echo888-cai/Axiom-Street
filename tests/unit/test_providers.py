from datetime import datetime, timezone

import pandas as pd

from quant.data.providers import _normalize


def test_normalize_adds_defaults():
    df = pd.DataFrame(
        [
            {
                "Date": datetime(2020, 1, 2, tzinfo=timezone.utc),
                "Open": 100,
                "High": 101,
                "Low": 99,
                "Close": 100.5,
                "Volume": 1000,
            }
        ]
    )
    out = _normalize(df, symbol="SPY")
    assert list(out.columns) == [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "dividends",
        "stock_splits",
        "exchange_timezone",
        "symbol",
    ]
    assert out.iloc[0]["symbol"] == "SPY"
    assert out.iloc[0]["dividends"] == 0.0
