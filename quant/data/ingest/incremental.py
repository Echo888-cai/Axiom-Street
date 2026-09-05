from __future__ import annotations

from pathlib import Path

import pandas as pd

from quant.data.ingest.snapshot import latest_snapshot_dir
from quant.data.types import QualityIssue


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
