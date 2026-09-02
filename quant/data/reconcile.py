"""Dual-source reconciliation for market data.

Close mismatches beyond a basis-point threshold are marked suspect.
Corporate-action disagreements are blocking — factor files must not be built
from contested dividend/split events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from quant.data.types import QualityIssue

CLOSE_BPS_THRESHOLD = 10.0  # 10 bps = 0.10%


@dataclass
class ReconcileReport:
    primary_source: str
    secondary_source: str
    compared_bars: int
    suspect_bars: int
    issues: list[QualityIssue] = field(default_factory=list)

    @property
    def has_blocking_issues(self) -> bool:
        return any(i.severity == "blocking" for i in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_source": self.primary_source,
            "secondary_source": self.secondary_source,
            "compared_bars": self.compared_bars,
            "suspect_bars": self.suspect_bars,
            "has_blocking_issues": self.has_blocking_issues,
            "issues": [
                {
                    "rule": i.rule,
                    "severity": i.severity,
                    "message": i.message,
                    "count": i.count,
                    "examples": i.examples[:5],
                }
                for i in self.issues
            ],
        }


def _aligned(primary: pd.DataFrame, secondary: pd.DataFrame) -> pd.DataFrame:
    left = primary.copy()
    right = secondary.copy()
    left["timestamp"] = pd.to_datetime(left["timestamp"], utc=True)
    right["timestamp"] = pd.to_datetime(right["timestamp"], utc=True)
    return left.merge(right, on="timestamp", suffixes=("_primary", "_secondary"), how="inner")


def reconcile_closes(
    primary: pd.DataFrame,
    secondary: pd.DataFrame,
    *,
    primary_source: str = "primary",
    secondary_source: str = "secondary",
    close_bps: float = CLOSE_BPS_THRESHOLD,
) -> ReconcileReport:
    """Flag overlapping bars whose close differs by more than ``close_bps``."""
    if close_bps <= 0:
        raise ValueError("close_bps must be positive")

    merged = _aligned(primary, secondary)
    if merged.empty:
        return ReconcileReport(
            primary_source=primary_source,
            secondary_source=secondary_source,
            compared_bars=0,
            suspect_bars=0,
            issues=[
                QualityIssue(
                    rule="dual_source_no_overlap",
                    severity="warning",
                    message=(
                        f"No overlapping timestamps between {primary_source} and "
                        f"{secondary_source}; reconciliation skipped."
                    ),
                    count=0,
                )
            ],
        )

    primary_close = merged["close_primary"].astype(float)
    secondary_close = merged["close_secondary"].astype(float)
    # Relative error in bps vs primary close; floor avoids division by zero.
    denom = primary_close.abs().clip(lower=1e-9)
    bps = ((secondary_close - primary_close).abs() / denom) * 10_000.0
    suspects = merged.loc[bps > close_bps]
    issues: list[QualityIssue] = []
    if not suspects.empty:
        examples = [
            f"{row.timestamp.date()} Δ={float(bps.loc[idx]):.1f}bps "
            f"({primary_source}={float(row.close_primary):.4f} vs "
            f"{secondary_source}={float(row.close_secondary):.4f})"
            for idx, row in suspects.head(5).iterrows()
        ]
        issues.append(
            QualityIssue(
                rule="dual_source_close_mismatch",
                severity="warning",
                message=(
                    f"Close differed by >{close_bps:g} bps between {primary_source} and "
                    f"{secondary_source}; bars marked suspect."
                ),
                count=int(len(suspects)),
                examples=examples,
            )
        )

    return ReconcileReport(
        primary_source=primary_source,
        secondary_source=secondary_source,
        compared_bars=int(len(merged)),
        suspect_bars=int(len(suspects)),
        issues=issues,
    )


def reconcile_corporate_actions(
    primary: pd.DataFrame,
    secondary: pd.DataFrame,
    *,
    primary_source: str = "primary",
    secondary_source: str = "secondary",
) -> list[QualityIssue]:
    """Require dividend/split events to agree on overlapping dates (fail-closed)."""
    merged = _aligned(primary, secondary)
    if merged.empty:
        return []

    issues: list[QualityIssue] = []
    for col, rule in (
        ("dividends", "dual_source_dividend_mismatch"),
        ("stock_splits", "dual_source_split_mismatch"),
    ):
        prior = merged[f"{col}_primary"].fillna(0.0).astype(float)
        other = merged[f"{col}_secondary"].fillna(0.0).astype(float)
        # Only compare dates where either side reports a non-zero event.
        active = (prior.abs() > 1e-12) | (other.abs() > 1e-12)
        bad = merged.loc[active & ((prior - other).abs() > 1e-9)]
        if bad.empty:
            continue
        examples = bad["timestamp"].dt.strftime("%Y-%m-%d").head(5).tolist()
        issues.append(
            QualityIssue(
                rule=rule,
                severity="blocking",
                message=(
                    f"{col} events disagree between {primary_source} and "
                    f"{secondary_source}; refusing contested corporate actions."
                ),
                count=int(len(bad)),
                examples=examples,
            )
        )
    return issues


def reconcile_frames(
    primary: pd.DataFrame,
    secondary: pd.DataFrame,
    *,
    primary_source: str,
    secondary_source: str,
    close_bps: float = CLOSE_BPS_THRESHOLD,
) -> ReconcileReport:
    """Full dual-source check: closes (warning) + corporate actions (blocking)."""
    report = reconcile_closes(
        primary,
        secondary,
        primary_source=primary_source,
        secondary_source=secondary_source,
        close_bps=close_bps,
    )
    report.issues.extend(
        reconcile_corporate_actions(
            primary,
            secondary,
            primary_source=primary_source,
            secondary_source=secondary_source,
        )
    )
    return report
