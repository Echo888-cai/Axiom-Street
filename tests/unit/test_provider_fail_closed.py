from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from quant.data.lean_converter import build_factor_file
from quant.data.providers import capabilities_for, fetch_spy_daily
from quant.data.types import STOOQ_CAPABILITIES, YFINANCE_CAPABILITIES, ProviderCapabilityError


def test_capabilities_stooq_has_no_corporate_actions():
    caps = capabilities_for("stooq")
    assert caps == STOOQ_CAPABILITIES
    assert caps.corporate_actions is False


def test_capabilities_yfinance_has_corporate_actions():
    assert capabilities_for("yfinance").corporate_actions is True
    assert YFINANCE_CAPABILITIES.dividends is True


def test_factor_file_requires_events_when_asked():
    df = pd.DataFrame(
        [
            {
                "timestamp": datetime(2020, 1, 2, tzinfo=timezone.utc),
                "open": 100,
                "high": 100,
                "low": 100,
                "close": 100,
                "volume": 1,
                "dividends": 0.0,
                "stock_splits": 0.0,
            }
        ]
    )
    with pytest.raises(ProviderCapabilityError):
        build_factor_file(df, require_corporate_actions=True)


def test_stooq_ingest_convert_raises(monkeypatch, tmp_path):
    from quant.data import ingest_spy as ingest_mod
    from quant.data.types import STOOQ_CAPABILITIES, FetchResult

    frame = pd.DataFrame(
        [
            {
                "timestamp": datetime(2020, 1, 2, tzinfo=timezone.utc),
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100.5,
                "volume": 1000,
                "dividends": 0.0,
                "stock_splits": 0.0,
            },
            {
                "timestamp": datetime(2020, 1, 3, tzinfo=timezone.utc),
                "open": 100.5,
                "high": 102,
                "low": 100,
                "close": 101,
                "volume": 1000,
                "dividends": 0.0,
                "stock_splits": 0.0,
            },
        ]
    )
    monkeypatch.setattr(
        ingest_mod,
        "fetch_daily",
        lambda *_a, **_k: FetchResult(frame, "stooq", STOOQ_CAPABILITIES),
    )
    with pytest.raises(ProviderCapabilityError, match="不提供分红"):
        ingest_mod.ingest_spy(data_root=tmp_path, convert_lean=True)


def test_fetch_spy_daily_auto_falls_back_to_stooq_then_raises_on_adjusted(monkeypatch):
    from quant.data import providers as providers_mod

    def boom(*_a, **_k):
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(providers_mod, "fetch_yfinance", boom)

    called = {}

    def fake_stooq(*_a, **_k):
        called["yes"] = True
        return pd.DataFrame(
            [
                {
                    "timestamp": datetime(2020, 1, 2, tzinfo=timezone.utc),
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "volume": 1,
                    "dividends": 0,
                    "stock_splits": 0,
                    "exchange_timezone": "America/New_York",
                    "symbol": "SPY",
                }
            ]
        )

    monkeypatch.setattr(providers_mod, "fetch_stooq", fake_stooq)
    result = fetch_spy_daily(provider="auto")
    assert called["yes"]
    assert result.source == "stooq"
    assert result.capabilities.corporate_actions is False
