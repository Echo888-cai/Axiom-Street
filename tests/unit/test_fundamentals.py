from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import pytest

from quant.data.fundamentals import (
    Fundamentals,
    FundamentalsFetchError,
    fetch_polygon_fundamentals,
    fundamentals_from_frame,
    load_fundamentals,
    save_fundamentals,
)


def test_roundtrip_parquet(tmp_path):
    payload = Fundamentals(
        symbol="AAPL",
        source="yfinance",
        shares=pd.DataFrame([{"as_of": date(2015, 1, 15), "shares_outstanding": 1_000_000.0}]),
        sector="Technology",
        industry="Consumer Electronics",
        sic=None,
        classified_as_of=date(2026, 9, 2),
    )
    save_fundamentals(tmp_path, payload)
    loaded = load_fundamentals(tmp_path, "AAPL")
    assert loaded is not None
    assert loaded.sector == "Technology"
    assert loaded.shares_as_of(date(2014, 12, 31)) is None
    assert loaded.shares_as_of(date(2015, 1, 15)) == 1_000_000.0
    assert loaded.classification_known_on(date(2026, 9, 1)) is False
    assert loaded.classification_known_on(date(2026, 9, 2)) is True


def test_empty_frame_is_rejected():
    empty = pd.DataFrame(
        columns=["as_of", "shares_outstanding", "sector", "industry", "sic", "source", "field"]
    )
    with pytest.raises(FundamentalsFetchError, match="为空"):
        fundamentals_from_frame("ZZZ", empty, source="test")


def test_polygon_uses_filing_date_not_period_end(monkeypatch):
    class FakeResp:
        def __init__(self, payload, status=200):
            self._payload = payload
            self.status_code = status
            self.text = "{}"

        def json(self):
            return self._payload

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def get(self, url, params=None):
            if "financials" in url:
                return FakeResp(
                    {
                        "results": [
                            {
                                "end_date": "2014-12-31",
                                "filing_date": "2015-01-28",
                                "financials": {
                                    "income_statement": {"weighted_average_shares": {"value": 42.0}}
                                },
                            }
                        ]
                    }
                )
            return FakeResp(
                {"results": {"sic_code": "3571", "sic_description": "ELECTRONIC COMPUTERS"}}
            )

    monkeypatch.setenv("POLYGON_API_KEY", "k")
    monkeypatch.setattr("httpx.Client", lambda **_k: FakeClient())
    payload = fetch_polygon_fundamentals("AAPL", start="2010-01-01")
    assert payload.shares_as_of(date(2015, 1, 27)) is None
    assert payload.shares_as_of(date(2015, 1, 28)) == 42.0
    assert payload.sector is None
    assert payload.industry == "ELECTRONIC COMPUTERS"


def test_ingest_writes_fundamentals(monkeypatch, tmp_path):
    from quant.data.ingest import ingest
    from quant.data.types import YFINANCE_CAPABILITIES, FetchResult

    rows = []
    for day in (2, 3, 6):
        rows.append(
            {
                "timestamp": datetime(2020, 1, day, tzinfo=timezone.utc),
                "open": 10,
                "high": 10,
                "low": 10,
                "close": 10,
                "volume": 100,
                "dividends": 0.0,
                "stock_splits": 0.0,
                "exchange_timezone": "America/New_York",
                "symbol": "SPY",
            }
        )
    frame = pd.DataFrame(rows)

    def fake_fetch(symbol: str, **_k):
        return FetchResult(frame.copy(), "yfinance", YFINANCE_CAPABILITIES)

    fund = Fundamentals(
        symbol="SPY",
        source="yfinance",
        shares=pd.DataFrame([{"as_of": date(2020, 1, 2), "shares_outstanding": 9e8}]),
        sector="Financial Services",
        industry="Asset Management",
        sic=None,
        classified_as_of=date(2020, 1, 6),
    )
    monkeypatch.setattr("quant.data.ingest.fetch_daily", fake_fetch)
    monkeypatch.setattr("quant.data.ingest.fetch_fundamentals", lambda symbol, **_k: fund)
    result = ingest(symbols=["SPY"], data_root=tmp_path, convert_lean=False)
    assert "SPY" in result["manifest"]["fundamentals_symbols"]
    loaded = load_fundamentals(tmp_path, "SPY")
    assert loaded is not None
    assert loaded.sector == "Financial Services"
