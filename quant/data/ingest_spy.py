from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from quant.data.lean_converter import convert_spy_to_lean
from quant.data.manifest import load_manifest, save_manifest
from quant.data.providers import fetch_spy_daily, provider_status
from quant.data.quality import validate_ohlcv
from quant.data.types import DataQualityError, ProviderCapabilityError


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


def ingest_spy(
    *,
    data_root: Optional[Path] = None,
    start: str = "2010-01-01",
    end: Optional[str] = None,
    provider: Optional[str] = None,
    convert_lean: bool = True,
) -> dict[str, Any]:
    """Download SPY daily bars into an immutable snapshot. Never overwrite a prior snapshot."""
    root = Path(data_root or os.getenv("AXIOM_DATA_ROOT") or _repo_data_root())
    fetched = fetch_spy_daily(
        provider=provider or os.getenv("AXIOM_DATA_PROVIDER") or "auto", start=start, end=end
    )
    frame = fetched.frame
    source = fetched.source
    caps = fetched.capabilities

    expected_end = pd.Timestamp(end, tz="UTC") if end else None
    report = validate_ohlcv(
        frame, expected_end=expected_end.to_pydatetime() if expected_end is not None else None
    )
    if report.has_blocking_issues:
        raise DataQualityError("SPY 数据质量校验未通过，拒绝写入快照。", report.to_dict())

    if convert_lean and not caps.corporate_actions:
        raise ProviderCapabilityError(f"数据源 {source} 不提供分红数据，无法进行调整价回测。")

    tmp = root / ".ingest_tmp_spy"
    if tmp.exists():
        shutil.rmtree(tmp)
    market_dir = tmp / "market" / "equities" / "US" / "daily"
    actions_dir = tmp / "corporate_actions"
    market_dir.mkdir(parents=True, exist_ok=True)
    actions_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = market_dir / "SPY.parquet"
    frame.to_parquet(parquet_path, index=False)
    actions = frame.loc[
        (frame["dividends"].fillna(0) != 0) | (frame["stock_splits"].fillna(0) != 0),
        ["timestamp", "dividends", "stock_splits"],
    ]
    actions.to_parquet(actions_dir / "SPY.parquet", index=False)

    digest = hashlib.sha256(parquet_path.read_bytes()).hexdigest()
    end_stamp = pd.to_datetime(frame["timestamp"].max(), utc=True).strftime("%Y%m%d")
    snapshot_key = f"spy-daily-{end_stamp}-{digest[:6]}"
    snap_dir = root / "snapshots" / snapshot_key
    snap_dir.parent.mkdir(parents=True, exist_ok=True)
    if snap_dir.exists():
        shutil.rmtree(tmp)
        manifest = load_manifest(snap_dir)
        return {
            "parquet": snap_dir / "market" / "equities" / "US" / "daily" / "SPY.parquet",
            "snapshot_key": snapshot_key,
            "content_sha256": digest,
            "deduplicated": True,
            "manifest": manifest,
            "quality_report": report.to_dict(),
        }

    tmp.rename(snap_dir)
    payload = {
        "symbol": "SPY",
        "resolution": "daily",
        "market": "US",
        "exchange_timezone": "America/New_York",
        "source": source,
        "start": str(frame["timestamp"].min()),
        "end": str(frame["timestamp"].max()),
        "rows": int(len(frame)),
        "sha256": digest,
        "snapshot_key": snapshot_key,
        "corporate_actions_verified": caps.corporate_actions,
        "provider_capabilities": {
            "ohlcv": caps.ohlcv,
            "dividends": caps.dividends,
            "splits": caps.splits,
            "point_in_time": caps.point_in_time,
        },
        "quality_report": report.to_dict(),
        "parquet": "market/equities/US/daily/SPY.parquet",
        "corporate_actions": "corporate_actions/SPY.parquet",
        "providers": provider_status(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_manifest(snap_dir, payload)

    if convert_lean:
        convert_spy_to_lean(snap_dir, require_corporate_actions=not caps.corporate_actions)

    _publish_latest(root, snap_dir)
    save_manifest(root, payload)

    return {
        "parquet": snap_dir / "market" / "equities" / "US" / "daily" / "SPY.parquet",
        "snapshot_key": snapshot_key,
        "content_sha256": digest,
        "deduplicated": False,
        "manifest": payload,
        "quality_report": report.to_dict(),
        "snapshot_dir": str(snap_dir),
    }


def load_spy_parquet(data_root: Optional[Path] = None) -> pd.DataFrame:
    root = Path(data_root or os.getenv("AXIOM_DATA_ROOT") or _repo_data_root())
    path = root / "market" / "equities" / "US" / "daily" / "SPY.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing SPY parquet at {path}. Run ingest_spy first.")
    return pd.read_parquet(path)


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
    parquet = root / "market" / "equities" / "US" / "daily" / "SPY.parquet"
    lean_zip = root / "lean" / "equity" / "usa" / "daily" / "spy.zip"
    manifest = load_manifest(root)
    latest = latest_snapshot_dir(root)
    quality = manifest.get("quality_report") or {}
    return {
        "ready": parquet.exists(),
        "lean_ready": lean_zip.exists(),
        "parquet_path": str(parquet) if parquet.exists() else None,
        "lean_path": str(lean_zip) if lean_zip.exists() else None,
        "manifest": manifest,
        "providers": provider_status(),
        "docker_required_for_backtest": True,
        "snapshot_key": manifest.get("snapshot_key"),
        "corporate_actions_verified": manifest.get("corporate_actions_verified"),
        "quality_report": quality,
        "latest_snapshot_dir": str(latest) if latest else None,
    }


if __name__ == "__main__":
    result = ingest_spy()
    print(
        json.dumps(
            {k: str(v) if isinstance(v, Path) else v for k, v in result.items()},
            indent=2,
            default=str,
        )
    )
    print(data_status())
