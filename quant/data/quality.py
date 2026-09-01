from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from quant.data.types import DataQualityReport, QualityIssue

MAX_GAP_CALENDAR_DAYS = 10
STALE_CALENDAR_DAYS = 14
JUMP_THRESHOLD = 0.5


def validate_ohlcv(
    frame: pd.DataFrame,
    *,
    as_of: datetime | None = None,
    expected_end: datetime | None = None,
) -> DataQualityReport:
    """Fail-closed quality checks for a daily OHLCV frame."""
    issues: list[QualityIssue] = []
    if frame.empty:
        issues.append(QualityIssue("empty", "blocking", "OHLCV frame is empty", count=0))
        return DataQualityReport(issues=issues, row_count=0, start=None, end=None)

    df = frame.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    start = df["timestamp"].min().to_pydatetime()
    end = df["timestamp"].max().to_pydatetime()

    if not df["timestamp"].is_monotonic_increasing:
        issues.append(
            QualityIssue("monotonic_dates", "blocking", "Timestamps are not strictly increasing")
        )

    df = df.sort_values("timestamp")

    dup = df["timestamp"].duplicated().sum()
    if dup:
        examples = df.loc[df["timestamp"].duplicated(), "timestamp"].astype(str).head(5).tolist()
        issues.append(
            QualityIssue(
                "duplicate_timestamps", "blocking", "Duplicate timestamps", int(dup), examples
            )
        )

    if not df["timestamp"].is_monotonic_increasing:
        issues.append(
            QualityIssue("monotonic_dates", "blocking", "Timestamps are not strictly increasing")
        )

    ohlc_bad = 0
    ohlc_examples: list[Any] = []
    for _, row in df.iterrows():
        o, h, low, c = (
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
        )
        if not (h >= max(o, c) and low <= min(o, c) and h >= low):
            ohlc_bad += 1
            if len(ohlc_examples) < 5:
                ohlc_examples.append(str(row["timestamp"]))
    if ohlc_bad:
        issues.append(
            QualityIssue(
                "ohlc_consistency", "blocking", "OHLC constraints violated", ohlc_bad, ohlc_examples
            )
        )

    non_pos = ((df["open"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["close"] <= 0)).sum()
    if non_pos:
        issues.append(
            QualityIssue("non_positive_prices", "blocking", "Non-positive prices", int(non_pos))
        )

    splits = df["stock_splits"].fillna(0) if "stock_splits" in df.columns else 0
    rets = df["close"].astype(float).pct_change()
    jump_mask = rets.abs() > JUMP_THRESHOLD
    if isinstance(splits, pd.Series):
        jump_mask = jump_mask & (splits.fillna(0) == 0)
    jump_n = int(jump_mask.sum()) if hasattr(jump_mask, "sum") else 0
    if jump_n:
        examples = df.loc[jump_mask, "timestamp"].astype(str).head(5).tolist()
        issues.append(
            QualityIssue(
                "price_jumps",
                "blocking",
                f"Close-to-close move > {JUMP_THRESHOLD:.0%} without a split event",
                jump_n,
                examples,
            )
        )

    zero_vol = int((df["volume"].fillna(0) <= 0).sum())
    if zero_vol:
        issues.append(
            QualityIssue("zero_volume", "warning", "Bars with zero or missing volume", zero_vol)
        )

    gap_n = 0
    gap_examples: list[Any] = []
    stamps = df["timestamp"].tolist()
    for prev, cur in zip(stamps, stamps[1:]):
        delta = (cur - prev).days
        if delta > MAX_GAP_CALENDAR_DAYS:
            gap_n += 1
            if len(gap_examples) < 5:
                gap_examples.append(f"{prev.date()} → {cur.date()} ({delta}d)")
    if gap_n:
        issues.append(
            QualityIssue(
                "trading_day_gaps",
                "blocking",
                f"Calendar gaps larger than {MAX_GAP_CALENDAR_DAYS} days",
                gap_n,
                gap_examples,
            )
        )

    as_of = as_of or datetime.now(timezone.utc)
    if expected_end is None:
        age = as_of - end if end.tzinfo else as_of.replace(tzinfo=None) - end
        if isinstance(age, timedelta) and age.days > STALE_CALENDAR_DAYS:
            issues.append(
                QualityIssue(
                    "stale_data",
                    "warning",
                    f"Last bar is {age.days} days old",
                    examples=[str(end)],
                )
            )

    return DataQualityReport(issues=issues, row_count=int(len(df)), start=start, end=end)
