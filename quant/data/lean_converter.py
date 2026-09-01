from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

from quant.data.manifest import load_manifest


def _write_zip_csv(zip_path: Path, inner_name: str, content: str) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(inner_name, content)


def bars_to_lean_daily_csv(df: pd.DataFrame) -> str:
    """Convert OHLCV to LEAN daily CSV (deci-cents prices)."""
    rows = []
    frame = df.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values("timestamp")
    for _, row in frame.iterrows():
        # LEAN equity daily timestamps are in New York; use 00:00 for daily bars
        ts = row["timestamp"].tz_convert("America/New_York")
        stamp = ts.strftime("%Y%m%d 00:00")
        o = int(round(float(row["open"]) * 10000))
        h = int(round(float(row["high"]) * 10000))
        lo = int(round(float(row["low"]) * 10000))
        c = int(round(float(row["close"]) * 10000))
        v = int(float(row["volume"]))
        rows.append(f"{stamp},{o},{h},{lo},{c},{v}")
    return "\n".join(rows) + "\n"


def build_factor_file(df: pd.DataFrame, *, require_corporate_actions: bool = False) -> str:
    """Build a minimal LEAN corporate factor file from dividends/splits.

    Format: date, price factor, split factor, reference price
    Factors are cumulative and applied going backwards in LEAN.
    """
    frame = df.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values("timestamp")

    price_factor = 1.0
    split_factor = 1.0
    events: list[tuple[pd.Timestamp, float, float, float]] = []

    for _, row in frame.iterrows():
        div = float(row.get("dividends") or 0.0)
        split = float(row.get("stock_splits") or 0.0)
        close = float(row["close"])
        changed = False
        if split and split != 0:
            split_factor *= 1.0 / split
            changed = True
        if div and div != 0 and close > 0:
            price_factor *= (close - div) / close
            changed = True
        if changed:
            ts = row["timestamp"].tz_convert("America/New_York")
            events.append((ts, price_factor, split_factor, close))

    if require_corporate_actions and not events:
        from quant.data.types import ProviderCapabilityError

        raise ProviderCapabilityError(
            "数据源不提供分红/拆分，无法生成调整因子文件，拒绝进行 Adjusted 模式回测。"
        )

    lines = ["20501231,1,1,0"]
    for ts, pf, sf, ref in reversed(events):
        lines.append(f"{ts.strftime('%Y%m%d')},{pf:.8f},{sf:.8f},{ref:.2f}")
    return "\n".join(lines) + "\n"


def _market_hours_segment(start: str, end: str, state: str) -> dict:
    return {"start": start, "end": end, "state": state}


def _default_equity_session() -> list[dict]:
    return [
        _market_hours_segment("04:00:00", "09:30:00", "premarket"),
        _market_hours_segment("09:30:00", "16:00:00", "market"),
        _market_hours_segment("16:00:00", "20:00:00", "postmarket"),
    ]


_SYMBOL_PROPS_HEADER = (
    "#SYM,SYM,securityType,market,quoteCurrency,contractMultiplier,"
    "minimumPriceVariation,lotSize,marketTicker,minimumOrderSize,"
    "priceMagnifier,strikeMultiplier\n"
)


def _ensure_symbol_property_row(path: Path, symbol: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size < 50:
        path.write_text(_SYMBOL_PROPS_HEADER, encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    needle = f"{symbol},"
    for line in text.splitlines():
        if line.startswith(needle) or line.startswith(f"{symbol.lower()},"):
            return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{symbol},{symbol},Equity,usa,USD,1,0.01,1,{symbol},1,1,1\n")


def ensure_lean_support_files(lean_root: Path, symbols: list[str] | None = None) -> None:
    """Ensure market-hours / symbol-properties / map files for the requested symbols.

    Prefer the official LEAN market-hours DB (copied from the Docker image).
    Only write a minimal stub when the official file is missing.
    """
    from quant.data.symbols import normalize_symbols

    tickers = normalize_symbols(symbols or ["SPY"])
    market_hours = lean_root / "market-hours" / "market-hours-database.json"
    market_hours.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite a large official file with a stub
    if not market_hours.exists() or market_hours.stat().st_size < 10_000:
        import json

        stub = {
            "entries": {
                "Equity-usa-[*]": {
                    "dataTimeZone": "America/New_York",
                    "exchangeTimeZone": "America/New_York",
                    "sunday": [],
                    "monday": _default_equity_session(),
                    "tuesday": _default_equity_session(),
                    "wednesday": _default_equity_session(),
                    "thursday": _default_equity_session(),
                    "friday": _default_equity_session(),
                    "saturday": [],
                }
            }
        }
        market_hours.write_text(json.dumps(stub, indent=2), encoding="utf-8")

    symbol_props = lean_root / "symbol-properties" / "symbol-properties-database.csv"
    for symbol in tickers:
        _ensure_symbol_property_row(symbol_props, symbol)
        map_file = lean_root / "equity" / "usa" / "map_files" / f"{symbol.lower()}.csv"
        map_file.parent.mkdir(parents=True, exist_ok=True)
        if not map_file.exists():
            lower = symbol.lower()
            map_file.write_text(f"20000101,{lower}\n20501231,{lower}\n", encoding="utf-8")


def convert_to_lean(
    data_root: Path,
    *,
    symbols: list[str] | None = None,
    require_corporate_actions: bool | None = None,
) -> Path:
    from quant.data.symbols import list_market_symbols, normalize_symbols

    root = Path(data_root)
    tickers = normalize_symbols(symbols or list_market_symbols(root) or ["SPY"])
    lean_root = root / "lean"
    ensure_lean_support_files(lean_root, tickers)

    if require_corporate_actions is None:
        manifest = load_manifest(root)
        require_corporate_actions = not bool(manifest.get("corporate_actions_verified", False))

    for symbol in tickers:
        parquet = root / "market" / "equities" / "US" / "daily" / f"{symbol}.parquet"
        if not parquet.exists():
            raise FileNotFoundError(f"Missing {symbol} parquet at {parquet}")
        df = pd.read_parquet(parquet)
        lower = symbol.lower()
        daily_zip = lean_root / "equity" / "usa" / "daily" / f"{lower}.zip"
        _write_zip_csv(daily_zip, f"{lower}.csv", bars_to_lean_daily_csv(df))
        factor_path = lean_root / "equity" / "usa" / "factor_files" / f"{lower}.csv"
        factor_path.parent.mkdir(parents=True, exist_ok=True)
        factor_path.write_text(
            build_factor_file(df, require_corporate_actions=require_corporate_actions),
            encoding="utf-8",
        )
    return lean_root


def convert_spy_to_lean(data_root: Path, *, require_corporate_actions: bool | None = None) -> Path:
    return convert_to_lean(
        data_root, symbols=["SPY"], require_corporate_actions=require_corporate_actions
    )


def ensure_lean_data(data_root: Path, symbols: list[str] | None = None) -> Path:
    from quant.data.symbols import list_market_symbols, normalize_symbols
    from quant.data.types import ProviderCapabilityError

    root = Path(data_root)
    tickers = normalize_symbols(symbols or list_market_symbols(root) or ["SPY"])
    lean_root = root / "lean"
    daily = root / "market" / "equities" / "US" / "daily"
    manifest = load_manifest(root)
    if manifest.get("corporate_actions_verified") is False:
        source = manifest.get("source") or "unknown"
        raise ProviderCapabilityError(f"数据源 {source} 不提供分红数据，无法进行调整价回测。")
    for symbol in tickers:
        parquet = daily / f"{symbol}.parquet"
        if not parquet.exists():
            raise FileNotFoundError(
                f"Missing {symbol} parquet at {parquet}. Ingest data before running a backtest."
            )
    need_convert = not bool(manifest)
    for symbol in tickers:
        parquet = daily / f"{symbol}.parquet"
        zip_path = lean_root / "equity" / "usa" / "daily" / f"{symbol.lower()}.zip"
        if not zip_path.exists() or parquet.stat().st_mtime > zip_path.stat().st_mtime:
            need_convert = True
            break
    if need_convert:
        return convert_to_lean(root, symbols=tickers)
    ensure_lean_support_files(lean_root, tickers)
    return lean_root


def ensure_lean_spy_data(data_root: Path) -> Path:
    return ensure_lean_data(data_root, symbols=["SPY"])
