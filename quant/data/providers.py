"""Market data providers for Phase 1.

Default path needs no API keys:
  1) yfinance (Yahoo)
  2) Stooq CSV fallback

Optional paid providers can be wired later via env keys
(POLYGON_API_KEY, ALPACA_*, ALPHA_VANTAGE_API_KEY, TIINGO_API_KEY).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from quant.data.types import (
    CAPABILITIES_BY_SOURCE,
    STOOQ_CAPABILITIES,
    YFINANCE_CAPABILITIES,
    FetchResult,
    ProviderCapabilities,
)

REQUIRED_COLS = [
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


def _normalize(frame: pd.DataFrame, symbol: str = "SPY") -> pd.DataFrame:
    df = frame.copy()
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    if "date" in df.columns and "timestamp" not in df.columns:
        df = df.rename(columns={"date": "timestamp"})
    if "datetime" in df.columns and "timestamp" not in df.columns:
        df = df.rename(columns={"datetime": "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["exchange_timezone"] = "America/New_York"
    df["symbol"] = symbol
    for col in ("dividends", "stock_splits"):
        if col not in df.columns:
            df[col] = 0.0
    for col in ("open", "high", "low", "close", "volume"):
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    return df[REQUIRED_COLS].sort_values("timestamp").reset_index(drop=True)


def fetch_yfinance(
    symbol: str = "SPY",
    start: str = "2010-01-01",
    end: Optional[str] = None,
) -> pd.DataFrame:
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    hist = ticker.history(start=start, end=end, auto_adjust=False, actions=True)
    if hist.empty:
        raise RuntimeError(f"yfinance returned empty history for {symbol}")
    hist = hist.reset_index()
    return _normalize(hist, symbol=symbol)


def fetch_stooq(
    symbol: str = "SPY",
    start: str = "2010-01-01",
    end: Optional[str] = None,
) -> pd.DataFrame:
    """Stooq daily bars — no API key. Corporate actions often unavailable."""
    # Stooq US symbols use .US suffix
    stooq_symbol = f"{symbol.lower()}.us"
    url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
    df = pd.read_csv(url)
    if df.empty or "Date" not in df.columns:
        raise RuntimeError(f"Stooq returned empty/invalid data for {symbol}")
    df = df.rename(
        columns={
            "Date": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    out = _normalize(df, symbol=symbol)
    start_ts = pd.Timestamp(start, tz="UTC")
    out = out[out["timestamp"] >= start_ts]
    if end:
        end_ts = pd.Timestamp(end, tz="UTC")
        out = out[out["timestamp"] <= end_ts]
    if out.empty:
        raise RuntimeError(f"Stooq filter produced empty frame for {symbol}")
    return out.reset_index(drop=True)


def fetch_spy_daily(
    *,
    provider: str = "auto",
    start: str = "2010-01-01",
    end: Optional[str] = None,
) -> FetchResult:
    """Return bars plus the provider's declared capabilities. auto = yfinance then stooq."""
    provider = (provider or "auto").lower()
    errors = []

    if provider in {"auto", "yfinance", "yahoo"}:
        try:
            frame = fetch_yfinance("SPY", start=start, end=end)
            return FetchResult(frame, "yfinance", YFINANCE_CAPABILITIES)
        except Exception as exc:
            errors.append(f"yfinance: {exc}")
            if provider != "auto":
                raise

    if provider in {"auto", "stooq"}:
        try:
            frame = fetch_stooq("SPY", start=start, end=end)
            return FetchResult(frame, "stooq", STOOQ_CAPABILITIES)
        except Exception as exc:
            errors.append(f"stooq: {exc}")
            if provider != "auto":
                raise

    raise RuntimeError("All data providers failed: " + " | ".join(errors))


def capabilities_for(source: str) -> ProviderCapabilities:
    return CAPABILITIES_BY_SOURCE.get(source, STOOQ_CAPABILITIES)


def provider_status() -> dict:
    return {
        "active": "auto (yfinance → stooq)",
        "requires_api_key": False,
        "optional_providers": {
            "polygon": {"env": ["POLYGON_API_KEY"], "wired": False},
            "alpaca": {
                "env": ["ALPACA_API_KEY", "ALPACA_API_SECRET"],
                "wired": False,
                "note": "Also used later for Paper Trading",
            },
            "alpha_vantage": {"env": ["ALPHA_VANTAGE_API_KEY"], "wired": False},
            "tiingo": {"env": ["TIINGO_API_KEY"], "wired": False},
        },
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
