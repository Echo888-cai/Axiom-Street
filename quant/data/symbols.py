from __future__ import annotations

import re
from pathlib import Path

_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def normalize_symbols(symbols: list[str] | str | None) -> list[str]:
    """Uppercase, dedupe, and reject empty/illegal tickers. Fail loud."""
    if symbols is None:
        raw: list[str] = ["SPY"]
    elif isinstance(symbols, str):
        raw = [part.strip() for part in symbols.replace(";", ",").split(",")]
    else:
        raw = list(symbols)

    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        symbol = str(item).strip().upper()
        if not symbol:
            continue
        if not _TICKER.fullmatch(symbol):
            raise ValueError(f"非法标的代码: {item}")
        if symbol not in seen:
            seen.add(symbol)
            out.append(symbol)
    if not out:
        raise ValueError("至少需要一个标的")
    return out


def as_symbol_list(value: object) -> list[str]:
    """Coerce manifest/DB `symbols` which may be a list or a comma string."""
    if value is None:
        return ["SPY"]
    if isinstance(value, str):
        return normalize_symbols(value)
    if isinstance(value, (list, tuple)):
        return normalize_symbols([str(item) for item in value])
    return ["SPY"]


def list_market_symbols(data_root: Path) -> list[str]:
    daily = Path(data_root) / "market" / "equities" / "US" / "daily"
    if not daily.exists():
        return []
    return sorted(path.stem.upper() for path in daily.glob("*.parquet"))


def load_symbols_file(path: Path | str) -> list[str]:
    """Load tickers from a text file (one per line; ``#`` comments allowed)."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"symbols file not found: {file_path}")
    raw: list[str] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if stripped:
            raw.append(stripped)
    if not raw:
        raise ValueError(f"{file_path} contains no tickers")
    return normalize_symbols(raw)


def snapshot_slug(symbols: list[str]) -> str:
    joined = "-".join(symbol.lower() for symbol in symbols)
    if len(joined) <= 48:
        return joined
    import hashlib

    digest = hashlib.sha256(",".join(symbols).encode("utf-8")).hexdigest()[:8]
    return f"eq{len(symbols)}-{digest}"
