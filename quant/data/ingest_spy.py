from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from quant.data.lean_converter import convert_to_lean
from quant.data.manifest import load_manifest, save_manifest
from quant.data.providers import fetch_daily, provider_status
from quant.data.quality import validate_ohlcv
from quant.data.symbols import list_market_symbols, normalize_symbols, snapshot_slug
from quant.data.types import (
    DataQualityError,
    DataQualityReport,
    ProviderCapabilityError,
    QualityIssue,
)


def _repo_data_root() -> Path:
    return Path(__file__).resolve().parents[2] / "data"


def _copy_tree(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def _publish_latest(root: Path, snap_dir: Path) -> None:
    """Point compatibility paths at the new snapshot without deleting history."""
    mapping = {
        "market": snap_dir / "market",
        "lean": snap_dir / "lean",
        "corporate_actions": snap_dir / "corporate_actions",
        "manifest.json": snap_dir / "manifest.json",
    }
    for name, src in mapping.items():
        dest = root / name
        if not src.exists():
            continue
        if dest.is_symlink():
            dest.unlink()
            dest.symlink_to(src if src.is_dir() else src, target_is_directory=src.is_dir())
        elif dest.exists() and dest.is_dir() and src.is_dir():
            _copy_tree(src, dest)
        elif src.is_file():
            shutil.copy2(src, dest)
        else:
            dest.symlink_to(src, target_is_directory=src.is_dir())


def _combined_quality(reports: list[DataQualityReport]) -> DataQualityReport:
    issues: list[QualityIssue] = []
    for report in reports:
        issues.extend(report.issues)
    starts = [r.start for r in reports if r.start is not None]
    ends = [r.end for r in reports if r.end is not None]
    return DataQualityReport(
        issues=issues,
        row_count=sum(r.row_count for r in reports),
        start=min(starts) if starts else None,
        end=max(ends) if ends else None,
    )


def ingest(
    *,
    symbols: list[str] | str | None = None,
    data_root: Optional[Path] = None,
    start: str = "2010-01-01",
    end: Optional[str] = None,
    provider: Optional[str] = None,
    convert_lean: bool = True,
) -> dict[str, Any]:
    """Download daily bars into an immutable snapshot. Never overwrite a prior snapshot."""
    tickers = normalize_symbols(symbols)
    root = Path(data_root or os.getenv("AXIOM_DATA_ROOT") or _repo_data_root())
    provider_name = provider or os.getenv("AXIOM_DATA_PROVIDER") or "auto"

    frames: dict[str, pd.DataFrame] = {}
    reports: list[DataQualityReport] = []
    sources: list[str] = []
    caps_ok = True
    last_caps = None

    for symbol in tickers:
        fetched = fetch_daily(symbol, provider=provider_name, start=start, end=end)
        frame = fetched.frame
        source = fetched.source
        caps = fetched.capabilities
        last_caps = caps
        sources.append(source)
        caps_ok = caps_ok and caps.corporate_actions

        expected_end = pd.Timestamp(end, tz="UTC") if end else None
        report = validate_ohlcv(
            frame, expected_end=expected_end.to_pydatetime() if expected_end is not None else None
        )
        if report.has_blocking_issues:
            raise DataQualityError(f"{symbol} 数据质量校验未通过，拒绝写入快照。", report.to_dict())
        if convert_lean and not caps.corporate_actions:
            raise ProviderCapabilityError(f"数据源 {source} 不提供分红数据，无法进行调整价回测。")
        frames[symbol] = frame
        reports.append(report)

    combined = _combined_quality(reports)
    tmp = root / ".ingest_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    market_dir = tmp / "market" / "equities" / "US" / "daily"
    actions_dir = tmp / "corporate_actions"
    market_dir.mkdir(parents=True, exist_ok=True)
    actions_dir.mkdir(parents=True, exist_ok=True)

    hasher = hashlib.sha256()
    max_ts = None
    min_ts = None
    total_rows = 0
    for symbol in tickers:
        frame = frames[symbol]
        parquet_path = market_dir / f"{symbol}.parquet"
        frame.to_parquet(parquet_path, index=False)
        hasher.update(symbol.encode("utf-8"))
        hasher.update(parquet_path.read_bytes())
        actions = frame.loc[
            (frame["dividends"].fillna(0) != 0) | (frame["stock_splits"].fillna(0) != 0),
            ["timestamp", "dividends", "stock_splits"],
        ]
        actions.to_parquet(actions_dir / f"{symbol}.parquet", index=False)
        total_rows += int(len(frame))
        ts_min = pd.to_datetime(frame["timestamp"].min(), utc=True)
        ts_max = pd.to_datetime(frame["timestamp"].max(), utc=True)
        min_ts = ts_min if min_ts is None else min(min_ts, ts_min)
        max_ts = ts_max if max_ts is None else max(max_ts, ts_max)

    digest = hasher.hexdigest()
    end_stamp = max_ts.strftime("%Y%m%d") if max_ts is not None else "unknown"
    snapshot_key = f"{snapshot_slug(tickers)}-daily-{end_stamp}-{digest[:6]}"
    snap_dir = root / "snapshots" / snapshot_key
    snap_dir.parent.mkdir(parents=True, exist_ok=True)
    if snap_dir.exists():
        shutil.rmtree(tmp)
        manifest = load_manifest(snap_dir)
        return {
            "parquet": snap_dir / "market" / "equities" / "US" / "daily" / f"{tickers[0]}.parquet",
            "snapshot_key": snapshot_key,
            "content_sha256": digest,
            "deduplicated": True,
            "manifest": manifest,
            "quality_report": combined.to_dict(),
            "symbols": tickers,
        }

    tmp.rename(snap_dir)
    unique_sources = list(dict.fromkeys(sources))
    source_label = unique_sources[0] if len(unique_sources) == 1 else "+".join(unique_sources)
    payload = {
        "symbol": tickers[0] if len(tickers) == 1 else ",".join(tickers),
        "symbols": tickers,
        "resolution": "daily",
        "market": "US",
        "exchange_timezone": "America/New_York",
        "source": source_label,
        "start": str(min_ts) if min_ts is not None else None,
        "end": str(max_ts) if max_ts is not None else None,
        "rows": total_rows,
        "sha256": digest,
        "snapshot_key": snapshot_key,
        "corporate_actions_verified": caps_ok,
        "provider_capabilities": {
            "ohlcv": True if last_caps is None else last_caps.ohlcv,
            "dividends": caps_ok,
            "splits": caps_ok,
            "point_in_time": False if last_caps is None else last_caps.point_in_time,
        },
        "quality_report": combined.to_dict(),
        "parquet": "market/equities/US/daily/" + ",".join(f"{s}.parquet" for s in tickers),
        "corporate_actions": "corporate_actions/" + ",".join(f"{s}.parquet" for s in tickers),
        "providers": provider_status(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_manifest(snap_dir, payload)

    if convert_lean:
        convert_to_lean(snap_dir, symbols=tickers, require_corporate_actions=not caps_ok)

    _publish_latest(root, snap_dir)
    save_manifest(root, payload)

    return {
        "parquet": snap_dir / "market" / "equities" / "US" / "daily" / f"{tickers[0]}.parquet",
        "snapshot_key": snapshot_key,
        "content_sha256": digest,
        "deduplicated": False,
        "manifest": payload,
        "quality_report": combined.to_dict(),
        "snapshot_dir": str(snap_dir),
        "symbols": tickers,
    }


def ingest_spy(
    *,
    data_root: Optional[Path] = None,
    start: str = "2010-01-01",
    end: Optional[str] = None,
    provider: Optional[str] = None,
    convert_lean: bool = True,
) -> dict[str, Any]:
    return ingest(
        symbols=["SPY"],
        data_root=data_root,
        start=start,
        end=end,
        provider=provider,
        convert_lean=convert_lean,
    )


def load_symbol_parquet(data_root: Optional[Path] = None, symbol: str = "SPY") -> pd.DataFrame:
    root = Path(data_root or os.getenv("AXIOM_DATA_ROOT") or _repo_data_root())
    ticker = normalize_symbols([symbol])[0]
    path = root / "market" / "equities" / "US" / "daily" / f"{ticker}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing {ticker} parquet at {path}. Run ingest first.")
    return pd.read_parquet(path)


def load_spy_parquet(data_root: Optional[Path] = None) -> pd.DataFrame:
    return load_symbol_parquet(data_root, "SPY")


def latest_snapshot_dir(data_root: Path) -> Path | None:
    snaps = data_root / "snapshots"
    if not snaps.exists():
        return None
    dirs = [p for p in snaps.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.stat().st_mtime)


def prune_unreferenced_snapshots(data_root: Path, referenced_keys: set[str]) -> list[str]:
    snaps = data_root / "snapshots"
    if not snaps.exists():
        return []
    removed: list[str] = []
    for path in snaps.iterdir():
        if path.is_dir() and path.name not in referenced_keys:
            shutil.rmtree(path)
            removed.append(path.name)
    return removed


def data_status(data_root: Optional[Path] = None) -> dict:
    root = Path(data_root or os.getenv("AXIOM_DATA_ROOT") or _repo_data_root())
    manifest = load_manifest(root)
    symbols = list_market_symbols(root)
    if not symbols:
        symbols = []
        raw = manifest.get("symbols") or manifest.get("symbol")
        if raw:
            try:
                from quant.data.symbols import as_symbol_list

                symbols = as_symbol_list(raw)
            except ValueError:
                symbols = []
    daily = root / "market" / "equities" / "US" / "daily"
    lean_daily = root / "lean" / "equity" / "usa" / "daily"
    ready = bool(symbols) and all((daily / f"{s}.parquet").exists() for s in symbols)
    lean_ready = bool(symbols) and all((lean_daily / f"{s.lower()}.zip").exists() for s in symbols)
    latest = latest_snapshot_dir(root)
    quality = manifest.get("quality_report") or {}
    first = symbols[0] if symbols else "SPY"
    parquet = daily / f"{first}.parquet"
    lean_zip = lean_daily / f"{first.lower()}.zip"
    return {
        "ready": ready,
        "lean_ready": lean_ready,
        "parquet_path": str(parquet) if parquet.exists() else None,
        "lean_path": str(lean_zip) if lean_zip.exists() else None,
        "manifest": manifest,
        "providers": provider_status(),
        "docker_required_for_backtest": True,
        "snapshot_key": manifest.get("snapshot_key"),
        "corporate_actions_verified": manifest.get("corporate_actions_verified"),
        "quality_report": quality,
        "latest_snapshot_dir": str(latest) if latest else None,
        "symbols": symbols,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest daily bars into an immutable snapshot.")
    parser.add_argument("symbols", nargs="*", default=["SPY"], help="Tickers, default SPY")
    parser.add_argument("--start", default="2010-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--provider", default="auto")
    parser.add_argument("--no-lean", action="store_true")
    args = parser.parse_args()
    result = ingest(
        symbols=args.symbols or ["SPY"],
        start=args.start,
        end=args.end,
        provider=args.provider,
        convert_lean=not args.no_lean,
    )
    print(
        json.dumps(
            {k: str(v) if isinstance(v, Path) else v for k, v in result.items()},
            indent=2,
            default=str,
        )
    )
    print(data_status())
