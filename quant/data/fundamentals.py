"""Point-in-time fundamentals for RULE universes.

Market cap is shares outstanding (as-of filing/vendor date) × unadjusted close.
Sector/industry is whatever the vendor reported on the fetch day — never
back-filled onto earlier bars. Missing fundamentals fail loud at rebuild;
price ingest records a warning and continues.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from quant.data.providers import _polygon_api_key, resolve_primary_provider
from quant.data.rate_limit import pace
from quant.data.symbols import normalize_symbols

FUNDAMENTALS_DIR = Path("fundamentals")


class FundamentalsFetchError(RuntimeError):
    """Vendor returned no usable point-in-time fundamentals."""


@dataclass(frozen=True)
class Fundamentals:
    symbol: str
    source: str
    shares: pd.DataFrame  # columns: as_of, shares_outstanding
    sector: str | None
    industry: str | None
    sic: str | None
    classified_as_of: date | None

    def has_shares(self) -> bool:
        return not self.shares.empty

    def has_classification(self) -> bool:
        return bool(self.sector or self.industry or self.sic)

    def shares_as_of(self, day: date) -> float | None:
        if self.shares.empty:
            return None
        eligible = self.shares.loc[self.shares["as_of"] <= day, "shares_outstanding"]
        if eligible.empty:
            return None
        value = float(eligible.iloc[-1])
        if value <= 0:
            return None
        return value

    def classification_known_on(self, day: date) -> bool:
        if self.classified_as_of is None or not self.has_classification():
            return False
        return day >= self.classified_as_of

    def to_frame(self) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for rec in self.shares.to_dict(orient="records"):
            rows.append(
                {
                    "as_of": rec["as_of"],
                    "shares_outstanding": rec["shares_outstanding"],
                    "sector": None,
                    "industry": None,
                    "sic": None,
                    "source": self.source,
                    "field": "shares",
                }
            )
        if self.has_classification() and self.classified_as_of is not None:
            rows.append(
                {
                    "as_of": self.classified_as_of,
                    "shares_outstanding": None,
                    "sector": self.sector,
                    "industry": self.industry,
                    "sic": self.sic,
                    "source": self.source,
                    "field": "classification",
                }
            )
        return pd.DataFrame(rows)


def fundamentals_dir(root: Path) -> Path:
    return Path(root) / FUNDAMENTALS_DIR


def fundamentals_path(root: Path, symbol: str) -> Path:
    ticker = normalize_symbols([symbol])[0]
    return fundamentals_dir(root) / f"{ticker}.parquet"


def save_fundamentals(root: Path, payload: Fundamentals) -> Path:
    path = fundamentals_path(root, payload.symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = payload.to_frame()
    if frame.empty:
        raise FundamentalsFetchError(f"{payload.symbol} 基本面为空，拒绝写入空文件")
    frame.to_parquet(path, index=False)
    return path


def fundamentals_from_frame(symbol: str, frame: pd.DataFrame, *, source: str) -> Fundamentals:
    if frame.empty:
        raise FundamentalsFetchError(f"{symbol} 基本面为空")
    df = frame.copy()
    df["as_of"] = pd.to_datetime(df["as_of"]).dt.date
    shares_rows = df[df["field"] == "shares"].sort_values("as_of")
    class_rows = df[df["field"] == "classification"].sort_values("as_of")
    shares = pd.DataFrame(
        {
            "as_of": list(shares_rows["as_of"]),
            "shares_outstanding": list(shares_rows["shares_outstanding"].astype(float)),
        }
    )
    sector = industry = sic = None
    classified_as_of = None
    if not class_rows.empty:
        last = class_rows.iloc[-1]
        sector = _optional_str(last.get("sector"))
        industry = _optional_str(last.get("industry"))
        sic = _optional_str(last.get("sic"))
        classified_as_of = last["as_of"]
    return Fundamentals(
        symbol=symbol,
        source=source,
        shares=shares,
        sector=sector,
        industry=industry,
        sic=sic,
        classified_as_of=classified_as_of,
    )


def load_fundamentals(data_root: Path, symbol: str) -> Fundamentals | None:
    path = fundamentals_path(data_root, symbol)
    if not path.exists():
        return None
    frame = pd.read_parquet(path)
    if frame.empty:
        return None
    source = str(frame["source"].iloc[-1]) if "source" in frame.columns else "unknown"
    return fundamentals_from_frame(symbol, frame, source=source)


def load_fundamentals_map(data_root: Path, symbols: list[str]) -> dict[str, Fundamentals]:
    out: dict[str, Fundamentals] = {}
    for symbol in symbols:
        item = load_fundamentals(data_root, symbol)
        if item is not None:
            out[symbol] = item
    return out


def fetch_fundamentals(
    symbol: str,
    *,
    provider: str = "auto",
    start: str = "2010-01-01",
) -> Fundamentals:
    ticker = normalize_symbols([symbol])[0]
    resolved = resolve_primary_provider(provider)
    if resolved == "polygon":
        return fetch_polygon_fundamentals(ticker, start=start)
    if resolved in {"auto", "yfinance", "yahoo"}:
        return fetch_yfinance_fundamentals(ticker, start=start)
    raise FundamentalsFetchError(
        f"数据源 {resolved} 不提供基本面；市值/行业规则需要 yfinance 或 polygon"
    )


def fetch_yfinance_fundamentals(symbol: str, *, start: str = "2010-01-01") -> Fundamentals:
    import yfinance as yf

    pace()
    ticker = yf.Ticker(symbol)
    try:
        shares_raw = ticker.get_shares_full(start=start)
    except Exception as exc:  # noqa: BLE001 — vendor SDK raises mixed types
        raise FundamentalsFetchError(f"{symbol} yfinance 股本序列失败: {exc}") from exc

    shares = _shares_from_series(shares_raw)
    pace()
    try:
        info = ticker.info or {}
    except Exception as exc:  # noqa: BLE001 — yfinance info is best-effort metadata
        raise FundamentalsFetchError(f"{symbol} yfinance info 失败: {exc}") from exc

    sector = _optional_str(info.get("sector"))
    industry = _optional_str(info.get("industry"))
    classified_as_of = datetime.now(timezone.utc).date() if (sector or industry) else None
    if shares.empty and not (sector or industry):
        raise FundamentalsFetchError(f"{symbol} yfinance 没有股本或行业分类")
    return Fundamentals(
        symbol=symbol,
        source="yfinance",
        shares=shares,
        sector=sector,
        industry=industry,
        sic=None,
        classified_as_of=classified_as_of,
    )


def fetch_polygon_fundamentals(
    symbol: str,
    *,
    start: str = "2010-01-01",
    api_key: str | None = None,
) -> Fundamentals:
    import httpx

    key = api_key if api_key is not None else _polygon_api_key()
    if not key:
        raise FundamentalsFetchError(
            "POLYGON_API_KEY is not set; refusing to call Polygon fundamentals."
        )

    with httpx.Client(timeout=30.0) as client:
        shares = _polygon_shares(client, symbol, start, key)
        sector, industry, sic = _polygon_classification(client, symbol, key)

    classified_as_of = datetime.now(timezone.utc).date() if (sector or industry or sic) else None
    if shares.empty and not (sector or industry or sic):
        raise FundamentalsFetchError(f"{symbol} Polygon 没有股本或行业分类")
    return Fundamentals(
        symbol=symbol,
        source="polygon",
        shares=shares,
        sector=sector,
        industry=industry,
        sic=sic,
        classified_as_of=classified_as_of,
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _shares_from_series(raw: object) -> pd.DataFrame:
    if raw is None:
        return pd.DataFrame(columns=["as_of", "shares_outstanding"])
    if isinstance(raw, pd.Series):
        series = raw.dropna()
    elif isinstance(raw, pd.DataFrame):
        if raw.empty:
            return pd.DataFrame(columns=["as_of", "shares_outstanding"])
        series = raw.iloc[:, 0].dropna()
    else:
        raise FundamentalsFetchError(f"无法解析股本序列: {type(raw).__name__}")
    if series.empty:
        return pd.DataFrame(columns=["as_of", "shares_outstanding"])
    rows = []
    for idx, value in series.items():
        day = pd.Timestamp(idx).date()
        shares = float(value)
        if shares <= 0:
            continue
        rows.append({"as_of": day, "shares_outstanding": shares})
    if not rows:
        return pd.DataFrame(columns=["as_of", "shares_outstanding"])
    return pd.DataFrame(rows).sort_values("as_of").reset_index(drop=True)


def _polygon_shares(client: Any, symbol: str, start: str, api_key: str) -> pd.DataFrame:
    url = "https://api.polygon.io/vX/reference/financials"
    rows: list[dict[str, Any]] = []
    params: dict[str, Any] = {
        "ticker": symbol,
        "limit": 100,
        "order": "asc",
        "sort": "filing_date",
        "filing_date.gte": start,
        "apiKey": api_key,
    }
    while url:
        pace()
        resp = client.get(url, params=params)
        params = {"apiKey": api_key}
        if resp.status_code >= 400:
            raise FundamentalsFetchError(
                f"Polygon financials failed ({resp.status_code}): {resp.text[:200]}"
            )
        payload = resp.json()
        for item in payload.get("results") or []:
            filing = str(item.get("filing_date") or "")[:10]
            if not filing:
                continue
            shares = _polygon_weighted_shares(item)
            if shares is None or shares <= 0:
                continue
            rows.append({"as_of": date.fromisoformat(filing), "shares_outstanding": shares})
        next_url = payload.get("next_url")
        url = str(next_url) if next_url else ""
    if not rows:
        return pd.DataFrame(columns=["as_of", "shares_outstanding"])
    frame = pd.DataFrame(rows).sort_values("as_of").drop_duplicates("as_of", keep="last")
    return frame.reset_index(drop=True)


def _polygon_weighted_shares(item: dict[str, Any]) -> float | None:
    financials = item.get("financials") or {}
    income = financials.get("income_statement") or {}
    for key in ("weighted_average_shares_diluted", "weighted_average_shares", "diluted_shares"):
        node = income.get(key) or {}
        if isinstance(node, dict) and node.get("value") is not None:
            return float(node["value"])
        if isinstance(node, (int, float)):
            return float(node)
    return None


def _polygon_classification(
    client: Any, symbol: str, api_key: str
) -> tuple[str | None, str | None, str | None]:
    url = f"https://api.polygon.io/v3/reference/tickers/{symbol}"
    pace()
    resp = client.get(url, params={"apiKey": api_key})
    if resp.status_code >= 400:
        raise FundamentalsFetchError(
            f"Polygon ticker details failed ({resp.status_code}): {resp.text[:200]}"
        )
    results = resp.json().get("results") or {}
    sic = _optional_str(results.get("sic_code"))
    industry = _optional_str(results.get("sic_description"))
    # Polygon does not publish GICS sector here. Do not invent one from SIC.
    return None, industry, sic
