from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

from quant.data.fundamentals import (
    Fundamentals,
    FundamentalsFetchError,
    fetch_fundamentals,
    save_fundamentals,
)
from quant.data.lean_converter import convert_to_lean
from quant.data.manifest import load_manifest, save_manifest
from quant.data.providers import (
    fetch_daily,
    provider_status,
    resolve_primary_provider,
    resolve_reconcile_with,
)
from quant.data.quality import validate_ohlcv
from quant.data.rate_limit import (
    ensure_ingest_symbol_count,
    ingest_concurrency,
    ingest_max_symbols,
    ingest_rps,
)
from quant.data.reconcile import reconcile_frames
from quant.data.symbols import (
    list_market_symbols,
    load_symbols_file,
    normalize_symbols,
    snapshot_slug,
)
from quant.data.types import (
    DataQualityError,
    DataQualityReport,
    ProviderCapabilityError,
    QualityIssue,
)
from quant.data.universe import inferred_delistings


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
        "fundamentals": snap_dir / "fundamentals",
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


def _prior_parquet_path(root: Path, symbol: str) -> Path | None:
    """Resolve prior bars from published latest path, then latest snapshot dir."""
    published = root / "market" / "equities" / "US" / "daily" / f"{symbol}.parquet"
    if published.exists():
        return published
    latest = latest_snapshot_dir(root)
    if latest is None:
        return None
    candidate = latest / "market" / "equities" / "US" / "daily" / f"{symbol}.parquet"
    return candidate if candidate.exists() else None


def _detect_restatements(prior: pd.DataFrame, incoming: pd.DataFrame) -> list[QualityIssue]:
    """Flag overlapping dates whose close/corp-actions differ (vendor restatement)."""
    left = prior.copy()
    right = incoming.copy()
    left["timestamp"] = pd.to_datetime(left["timestamp"], utc=True)
    right["timestamp"] = pd.to_datetime(right["timestamp"], utc=True)
    merged = left.merge(right, on="timestamp", suffixes=("_prior", "_new"), how="inner")
    if merged.empty:
        return []
    close_delta = (merged["close_new"] - merged["close_prior"]).abs()
    # 1 bp on prior close, floor at 1e-6 absolute
    threshold = (merged["close_prior"].abs() * 1e-4).clip(lower=1e-6)
    changed = close_delta > threshold
    for col in ("dividends", "stock_splits"):
        prior_col, new_col = f"{col}_prior", f"{col}_new"
        if prior_col in merged.columns and new_col in merged.columns:
            changed = (
                changed | (merged[prior_col].fillna(0.0) - merged[new_col].fillna(0.0)).abs() > 1e-9
            )
    bad = merged.loc[changed]
    if bad.empty:
        return []
    examples = bad["timestamp"].dt.strftime("%Y-%m-%d").head(5).tolist()
    return [
        QualityIssue(
            rule="vendor_restatement",
            severity="warning",
            message=(
                "Vendor restated overlapping history; wrote a new immutable snapshot "
                "(prior snapshot left untouched)."
            ),
            count=int(len(bad)),
            examples=examples,
        )
    ]


def _merge_incremental(
    prior: pd.DataFrame, incoming: pd.DataFrame
) -> tuple[pd.DataFrame, list[QualityIssue]]:
    issues = _detect_restatements(prior, incoming)
    left = prior.copy()
    right = incoming.copy()
    left["timestamp"] = pd.to_datetime(left["timestamp"], utc=True)
    right["timestamp"] = pd.to_datetime(right["timestamp"], utc=True)
    # Prefer incoming values on overlap (vendor revision wins), keep prior-only rows.
    combined = pd.concat([left, right], ignore_index=True)
    combined = combined.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    combined = combined.reset_index(drop=True)
    return combined, issues


def _ingest_one_symbol(
    symbol: str,
    *,
    root: Path,
    start: str,
    end: Optional[str],
    provider_name: str,
    mode: str,
    reconcile_provider: str | None,
    convert_lean: bool,
) -> dict[str, Any]:
    fetch_start = start
    prior_frame: pd.DataFrame | None = None
    prior_path = _prior_parquet_path(root, symbol)
    if prior_path is not None:
        prior_frame = pd.read_parquet(prior_path)
        if prior_frame is not None and prior_frame.empty:
            prior_frame = None

    if mode == "incremental":
        if prior_frame is None:
            raise ValueError(
                f"incremental ingest requires prior bars for {symbol}; "
                "run mode='full' once before incremental updates."
            )
        last_ts = pd.to_datetime(prior_frame["timestamp"], utc=True).max()
        fetch_start = (last_ts + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    fetched = fetch_daily(symbol, provider=provider_name, start=fetch_start, end=end)
    frame = fetched.frame
    source = fetched.source
    caps = fetched.capabilities

    restatement_issues: list[QualityIssue] = []
    if mode == "incremental":
        assert prior_frame is not None
        if frame.empty:
            frame = prior_frame.copy()
        else:
            frame, restatement_issues = _merge_incremental(prior_frame, frame)
    elif mode == "full" and prior_frame is not None and not frame.empty:
        restatement_issues = _detect_restatements(prior_frame, frame)

    expected_end = pd.Timestamp(end, tz="UTC") if end else None
    report = validate_ohlcv(
        frame, expected_end=expected_end.to_pydatetime() if expected_end is not None else None
    )
    report.issues.extend(restatement_issues)

    recon_payload: dict[str, Any] | None = None
    if reconcile_provider:
        frame_start = pd.to_datetime(frame["timestamp"], utc=True).min().strftime("%Y-%m-%d")
        frame_end = pd.to_datetime(frame["timestamp"], utc=True).max().strftime("%Y-%m-%d")
        secondary = fetch_daily(
            symbol, provider=reconcile_provider, start=frame_start, end=frame_end
        )
        recon = reconcile_frames(
            frame,
            secondary.frame,
            primary_source=source,
            secondary_source=secondary.source,
        )
        report.issues.extend(recon.issues)
        recon_payload = {"symbol": symbol, **recon.to_dict()}

    if report.has_blocking_issues:
        raise DataQualityError(f"{symbol} 数据质量校验未通过，拒绝写入快照。", report.to_dict())
    if convert_lean and not caps.corporate_actions:
        raise ProviderCapabilityError(f"数据源 {source} 不提供分红数据，无法进行调整价回测。")

    fundamentals: Fundamentals | None = None
    try:
        fundamentals = fetch_fundamentals(symbol, provider=source, start=fetch_start)
    except FundamentalsFetchError as exc:
        report.issues.append(
            QualityIssue(
                rule="fundamentals_unavailable",
                severity="warning",
                message=(
                    f"{symbol} 基本面不可用，市值/行业规则将无法使用该标的"
                    f"（不会用当前市值回填历史）: {exc}"
                ),
            )
        )

    return {
        "symbol": symbol,
        "frame": frame,
        "source": source,
        "caps": caps,
        "report": report,
        "fetch_window": {"start": fetch_start, "end": end},
        "reconcile_report": recon_payload,
        "fundamentals": fundamentals,
    }


def _fetch_universe(
    tickers: list[str],
    *,
    root: Path,
    start: str,
    end: Optional[str],
    provider_name: str,
    mode: str,
    reconcile_provider: str | None,
    convert_lean: bool,
    on_progress: Callable[[str, int, int], None] | None,
) -> list[dict[str, Any]]:
    workers = ingest_concurrency()
    completed = 0
    lock = threading.Lock()
    by_symbol: dict[str, dict[str, Any]] = {}

    def run(symbol: str) -> None:
        nonlocal completed
        item = _ingest_one_symbol(
            symbol,
            root=root,
            start=start,
            end=end,
            provider_name=provider_name,
            mode=mode,
            reconcile_provider=reconcile_provider,
            convert_lean=convert_lean,
        )
        with lock:
            by_symbol[symbol] = item
            completed += 1
            if on_progress is not None:
                on_progress(symbol, completed, len(tickers))

    if workers <= 1 or len(tickers) <= 1:
        for symbol in tickers:
            run(symbol)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(run, symbol) for symbol in tickers]
            try:
                for fut in as_completed(futures):
                    fut.result()
            except Exception:
                for fut in futures:
                    fut.cancel()
                raise
    return [by_symbol[symbol] for symbol in tickers]


def ingest(
    *,
    symbols: list[str] | str | None = None,
    data_root: Optional[Path] = None,
    start: str = "2010-01-01",
    end: Optional[str] = None,
    provider: Optional[str] = None,
    convert_lean: bool = True,
    mode: str = "full",
    reconcile_with: str | None = None,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, Any]:
    """Download daily bars into an immutable snapshot. Never overwrite a prior snapshot.

    mode:
      - full: fetch [start, end] for every symbol. If a prior snapshot exists,
        overlapping bars that changed become ``vendor_restatement`` warnings;
        the prior snapshot is never mutated.
      - incremental: require prior bars; fetch only after each symbol's last bar;
        concat into a new snapshot. Restatements are warnings, never in-place edits.

    reconcile_with:
      Optional secondary provider (e.g. ``yfinance`` when primary is ``polygon``).
      Close mismatches become warnings; corporate-action disagreements block.

    on_progress:
      Optional ``(symbol, index_1based, total)`` callback for batch progress UIs.
    """
    if mode not in {"full", "incremental"}:
        raise ValueError(f"unsupported ingest mode: {mode!r} (expected 'full' or 'incremental')")

    tickers = normalize_symbols(symbols)
    ensure_ingest_symbol_count(len(tickers))
    root = Path(data_root or os.getenv("STREET_DATA_ROOT") or _repo_data_root())
    provider_name = resolve_primary_provider(provider)
    reconcile_provider = resolve_reconcile_with(provider_name, reconcile_with)

    frames: dict[str, pd.DataFrame] = {}
    reports: list[DataQualityReport] = []
    sources: list[str] = []
    reconcile_reports: list[dict[str, Any]] = []
    fundamentals_by_symbol: dict[str, Fundamentals] = {}
    caps_ok = True
    last_caps = None
    fetch_windows: dict[str, dict[str, str | None]] = {}
    prior_snapshot_key = load_manifest(root).get("snapshot_key")

    fetched_rows = _fetch_universe(
        tickers,
        root=root,
        start=start,
        end=end,
        provider_name=provider_name,
        mode=mode,
        reconcile_provider=reconcile_provider,
        convert_lean=convert_lean,
        on_progress=on_progress,
    )
    for item in fetched_rows:
        symbol = item["symbol"]
        frames[symbol] = item["frame"]
        reports.append(item["report"])
        sources.append(item["source"])
        last_caps = item["caps"]
        caps_ok = caps_ok and item["caps"].corporate_actions
        fetch_windows[symbol] = item["fetch_window"]
        if item["reconcile_report"] is not None:
            reconcile_reports.append(item["reconcile_report"])
        if item.get("fundamentals") is not None:
            fundamentals_by_symbol[symbol] = item["fundamentals"]

    last_bars: dict[str, date] = {}
    for symbol, frame in frames.items():
        ts_max = pd.to_datetime(frame["timestamp"].max(), utc=True)
        last_bars[symbol] = ts_max.date()
    delistings = inferred_delistings(last_bars)

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

    fund_dir = tmp / "fundamentals"
    if fundamentals_by_symbol:
        fund_dir.mkdir(parents=True, exist_ok=True)
        for symbol, fund in fundamentals_by_symbol.items():
            path = save_fundamentals(tmp, fund)
            hasher.update(symbol.encode("utf-8"))
            hasher.update(b"fundamentals")
            hasher.update(path.read_bytes())

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
            "inferred_delistings": delistings,
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
        "ingest_mode": mode,
        "fetch_windows": fetch_windows,
        "prior_snapshot_key": prior_snapshot_key,
        "reconcile_with": reconcile_provider,
        "reconcile_reports": reconcile_reports,
        "inferred_delistings": delistings,
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
        "fundamentals_symbols": sorted(fundamentals_by_symbol),
        "fundamentals": (
            "fundamentals/" + ",".join(f"{s}.parquet" for s in sorted(fundamentals_by_symbol))
            if fundamentals_by_symbol
            else None
        ),
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
        "ingest_mode": mode,
        "fetch_windows": fetch_windows,
        "prior_snapshot_key": prior_snapshot_key,
        "reconcile_with": reconcile_provider,
        "reconcile_reports": reconcile_reports,
        "inferred_delistings": delistings,
    }


def ingest_spy(
    *,
    data_root: Optional[Path] = None,
    start: str = "2010-01-01",
    end: Optional[str] = None,
    provider: Optional[str] = None,
    convert_lean: bool = True,
    mode: str = "full",
    reconcile_with: str | None = None,
) -> dict[str, Any]:
    return ingest(
        symbols=["SPY"],
        data_root=data_root,
        start=start,
        end=end,
        provider=provider,
        convert_lean=convert_lean,
        mode=mode,
        reconcile_with=reconcile_with,
    )


def load_symbol_parquet(data_root: Optional[Path] = None, symbol: str = "SPY") -> pd.DataFrame:
    root = Path(data_root or os.getenv("STREET_DATA_ROOT") or _repo_data_root())
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
    root = Path(data_root or os.getenv("STREET_DATA_ROOT") or _repo_data_root())
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
    first = symbols[0] if symbols else None
    parquet = daily / f"{first}.parquet" if first else daily / "_none.parquet"
    lean_zip = lean_daily / f"{first.lower()}.zip" if first else lean_daily / "_none.zip"
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
        "reconcile_with": manifest.get("reconcile_with"),
        "reconcile_reports": manifest.get("reconcile_reports") or [],
        "inferred_delistings": manifest.get("inferred_delistings") or [],
        "ingest_limits": {
            "max_symbols": ingest_max_symbols(),
            "rps": ingest_rps(),
            "concurrency": ingest_concurrency(),
        },
        "fundamentals_symbols": manifest.get("fundamentals_symbols") or [],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest daily bars into an immutable snapshot.")
    parser.add_argument("symbols", nargs="*", default=None, help="Tickers; default SPY if omitted")
    parser.add_argument(
        "--symbols-file",
        default=None,
        help="text file with one ticker per line (# comments allowed)",
    )
    parser.add_argument("--start", default="2010-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--provider", default="auto")
    parser.add_argument(
        "--mode",
        choices=("full", "incremental"),
        default="full",
        help="full = refetch history; incremental = append after last bar",
    )
    parser.add_argument(
        "--reconcile-with",
        default=None,
        help="optional secondary provider for dual-source reconciliation (e.g. yfinance)",
    )
    parser.add_argument("--no-lean", action="store_true")
    args = parser.parse_args()
    tickers = list(args.symbols or [])
    if args.symbols_file:
        tickers.extend(load_symbols_file(args.symbols_file))
    result = ingest(
        symbols=tickers or ["SPY"],
        start=args.start,
        end=args.end,
        provider=args.provider,
        convert_lean=not args.no_lean,
        mode=args.mode,
        reconcile_with=args.reconcile_with,
    )
    print(
        json.dumps(
            {k: str(v) if isinstance(v, Path) else v for k, v in result.items()},
            indent=2,
            default=str,
        )
    )
    print(data_status())
