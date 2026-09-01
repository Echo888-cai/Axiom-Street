from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional

import pandas as pd

from quant.data.manifest import load_manifest, save_manifest
from quant.data.providers import fetch_spy_daily, provider_status


def _repo_data_root() -> Path:
    return Path(__file__).resolve().parents[2] / "data"


def ingest_spy(
    *,
    data_root: Optional[Path] = None,
    start: str = "2010-01-01",
    end: Optional[str] = None,
    provider: Optional[str] = None,
    convert_lean: bool = True,
) -> Path:
    """Download SPY daily bars and write Parquet + manifest (+ LEAN files)."""
    root = Path(data_root or os.getenv("AXIOM_DATA_ROOT") or _repo_data_root())
    out_dir = root / "market" / "equities" / "US" / "daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    actions_dir = root / "corporate_actions"
    actions_dir.mkdir(parents=True, exist_ok=True)

    source_name = provider or os.getenv("AXIOM_DATA_PROVIDER") or "auto"
    frame, source = fetch_spy_daily(provider=source_name, start=start, end=end)

    parquet_path = out_dir / "SPY.parquet"
    frame.to_parquet(parquet_path, index=False)

    actions = frame.loc[
        (frame["dividends"].fillna(0) != 0) | (frame["stock_splits"].fillna(0) != 0),
        ["timestamp", "dividends", "stock_splits"],
    ]
    actions_path = actions_dir / "SPY.parquet"
    actions.to_parquet(actions_path, index=False)

    digest = hashlib.sha256(parquet_path.read_bytes()).hexdigest()
    save_manifest(
        root,
        {
            "symbol": "SPY",
            "resolution": "daily",
            "market": "US",
            "exchange_timezone": "America/New_York",
            "source": source,
            "start": str(frame["timestamp"].min()),
            "end": str(frame["timestamp"].max()),
            "rows": int(len(frame)),
            "sha256": digest,
            "parquet": str(parquet_path.relative_to(root)),
            "corporate_actions": str(actions_path.relative_to(root)),
            "providers": provider_status(),
        },
    )

    if convert_lean:
        from quant.data.lean_converter import convert_spy_to_lean

        convert_spy_to_lean(root)

    return parquet_path


def load_spy_parquet(data_root: Optional[Path] = None) -> pd.DataFrame:
    root = Path(data_root or os.getenv("AXIOM_DATA_ROOT") or _repo_data_root())
    path = root / "market" / "equities" / "US" / "daily" / "SPY.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing SPY parquet at {path}. Run ingest_spy first.")
    return pd.read_parquet(path)


def data_status(data_root: Optional[Path] = None) -> dict:
    root = Path(data_root or os.getenv("AXIOM_DATA_ROOT") or _repo_data_root())
    parquet = root / "market" / "equities" / "US" / "daily" / "SPY.parquet"
    lean_zip = root / "lean" / "equity" / "usa" / "daily" / "spy.zip"
    manifest = load_manifest(root)
    return {
        "ready": parquet.exists(),
        "lean_ready": lean_zip.exists(),
        "parquet_path": str(parquet) if parquet.exists() else None,
        "lean_path": str(lean_zip) if lean_zip.exists() else None,
        "manifest": manifest,
        "providers": provider_status(),
        "docker_required_for_backtest": True,
    }


if __name__ == "__main__":
    path = ingest_spy()
    print(f"Wrote {path}")
    print(data_status())
