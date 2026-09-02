"""Market data providers.

Default path needs no API keys:
  1) yfinance (Yahoo)
  2) Stooq CSV fallback

Polygon is wired as an optional primary source. When selected without
``POLYGON_API_KEY``, the call fails loud — never silently degrades.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from quant.data.symbols import normalize_symbols
from quant.data.types import (
    CAPABILITIES_BY_SOURCE,
    POLYGON_CAPABILITIES,
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


def _polygon_api_key() -> str | None:
    key = (os.getenv("POLYGON_API_KEY") or "").strip()
    return key or None


def fetch_polygon(
    symbol: str = "SPY",
    start: str = "2010-01-01",
    end: Optional[str] = None,
    *,
    api_key: str | None = None,
) -> pd.DataFrame:
    """Fetch daily aggregates + corporate actions from Polygon.

    Requires ``POLYGON_API_KEY``. Missing key or HTTP failure raises — no fallback.
    """
    import httpx

    key = (api_key if api_key is not None else _polygon_api_key())
    if not key:
        raise RuntimeError(
            "POLYGON_API_KEY is not set; refusing to call Polygon. "
            "Set the key or use provider=yfinance|auto."
        )

    end_day = end or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    agg_url = (
        f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/"
        f"{start}/{end_day}"
    )
    with httpx.Client(timeout=30.0) as client:
        agg_resp = client.get(agg_url, params={"adjusted": "false", "sort": "asc", "limit": 50000, "apiKey": key})
        if agg_resp.status_code == 401 or agg_resp.status_code == 403:
            raise RuntimeError(f"Polygon authentication failed ({agg_resp.status_code})")
        if agg_resp.status_code >= 400:
            raise RuntimeError(f"Polygon aggregates failed ({agg_resp.status_code}): {agg_resp.text[:200]}")
        payload = agg_resp.json()
        results = payload.get("results") or []
        if not results:
            raise RuntimeError(f"Polygon returned empty aggregates for {symbol}")

        dividends = _polygon_dividends(client, symbol, start, end_day, key)
        splits = _polygon_splits(client, symbol, start, end_day, key)

    rows = []
    for bar in results:
        ts = pd.to_datetime(int(bar["t"]), unit="ms", utc=True)
        day = ts.strftime("%Y-%m-%d")
        rows.append(
            {
                "timestamp": ts.normalize(),
                "open": float(bar["o"]),
                "high": float(bar["h"]),
                "low": float(bar["l"]),
                "close": float(bar["c"]),
                "volume": float(bar.get("v") or 0),
                "dividends": float(dividends.get(day, 0.0)),
                "stock_splits": float(splits.get(day, 0.0)),
            }
        )
    return _normalize(pd.DataFrame(rows), symbol=symbol)


def _polygon_dividends(
    client: object, symbol: str, start: str, end: str, api_key: str
) -> dict[str, float]:
    import httpx

    assert isinstance(client, httpx.Client)
    url = "https://api.polygon.io/v3/reference/dividends"
    resp = client.get(
        url,
        params={
            "ticker": symbol,
            "ex_dividend_date.gte": start,
            "ex_dividend_date.lte": end,
            "limit": 1000,
            "apiKey": api_key,
        },
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Polygon dividends failed ({resp.status_code}): {resp.text[:200]}")
    out: dict[str, float] = {}
    for item in resp.json().get("results") or []:
        day = str(item.get("ex_dividend_date") or "")[:10]
        if not day:
            continue
        out[day] = out.get(day, 0.0) + float(item.get("cash_amount") or 0.0)
    return out


def _polygon_splits(
    client: object, symbol: str, start: str, end: str, api_key: str
) -> dict[str, float]:
    import httpx

    assert isinstance(client, httpx.Client)
    url = "https://api.polygon.io/v3/reference/splits"
    resp = client.get(
        url,
        params={
            "ticker": symbol,
            "execution_date.gte": start,
            "execution_date.lte": end,
            "limit": 1000,
            "apiKey": api_key,
        },
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Polygon splits failed ({resp.status_code}): {resp.text[:200]}")
    out: dict[str, float] = {}
    for item in resp.json().get("results") or []:
        day = str(item.get("execution_date") or "")[:10]
        if not day:
            continue
        # Polygon split ratio = split_to / split_from (e.g. 4/1 → 4.0)
        split_to = float(item.get("split_to") or 0.0)
        split_from = float(item.get("split_from") or 0.0)
        if split_from <= 0:
            continue
        out[day] = split_to / split_from
    return out


def fetch_daily(
    symbol: str,
    *,
    provider: str = "auto",
    start: str = "2010-01-01",
    end: Optional[str] = None,
) -> FetchResult:
    """Return bars plus the provider's declared capabilities.

    auto = yfinance then stooq. polygon is opt-in and never a silent fallback.
    """
    symbol = normalize_symbols([symbol])[0]
    provider = (provider or "auto").lower()
    errors = []

    if provider == "polygon":
        frame = fetch_polygon(symbol, start=start, end=end)
        return FetchResult(frame, "polygon", POLYGON_CAPABILITIES)

    if provider in {"auto", "yfinance", "yahoo"}:
        try:
            frame = fetch_yfinance(symbol, start=start, end=end)
            return FetchResult(frame, "yfinance", YFINANCE_CAPABILITIES)
        except Exception as exc:
            errors.append(f"yfinance: {exc}")
            if provider != "auto":
                raise

    if provider in {"auto", "stooq"}:
        try:
            frame = fetch_stooq(symbol, start=start, end=end)
            return FetchResult(frame, "stooq", STOOQ_CAPABILITIES)
        except Exception as exc:
            errors.append(f"stooq: {exc}")
            if provider != "auto":
                raise

    raise RuntimeError(f"All data providers failed for {symbol}: " + " | ".join(errors))


def fetch_spy_daily(
    *,
    provider: str = "auto",
    start: str = "2010-01-01",
    end: Optional[str] = None,
) -> FetchResult:
    return fetch_daily("SPY", provider=provider, start=start, end=end)


def capabilities_for(source: str) -> ProviderCapabilities:
    return CAPABILITIES_BY_SOURCE.get(source, STOOQ_CAPABILITIES)


def provider_status() -> dict:
    polygon_key = bool(_polygon_api_key())
    return {
        "active": "auto (yfinance → stooq)",
        "requires_api_key": False,
        "optional_providers": {
            "polygon": {
                "env": ["POLYGON_API_KEY"],
                "wired": True,
                "configured": polygon_key,
                "role": "optional primary; pair with yfinance via reconcile_with",
            },
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
