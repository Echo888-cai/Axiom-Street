"""Point-in-time universe filters evaluated on ingested bars.

Market-cap / sector screens need a fundamentals vendor we do not have yet.
Liquidity and price are computed from the snapshot so a RULE universe cannot
invent constituents that were never in the data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from quant.data.universe import Membership, validate_memberships

ALLOWED_RULE_KEYS = frozenset({"min_price", "min_adv_usd", "lookback_days"})
DEFAULT_LOOKBACK_DAYS = 21


@dataclass(frozen=True)
class UniverseRuleSet:
    min_price: float | None = None
    min_adv_usd: float | None = None
    lookback_days: int = DEFAULT_LOOKBACK_DAYS

    def to_dict(self) -> dict[str, float | int]:
        payload: dict[str, float | int] = {"lookback_days": self.lookback_days}
        if self.min_price is not None:
            payload["min_price"] = self.min_price
        if self.min_adv_usd is not None:
            payload["min_adv_usd"] = self.min_adv_usd
        return payload


def parse_rules(raw: object) -> UniverseRuleSet:
    if raw is None:
        raise ValueError("RULE 标的池必须提供 rules")
    if not isinstance(raw, dict):
        raise ValueError("rules 必须是对象")
    unknown = sorted(set(raw) - ALLOWED_RULE_KEYS)
    if unknown:
        raise ValueError(f"未知规则字段: {unknown}")

    lookback = raw.get("lookback_days", DEFAULT_LOOKBACK_DAYS)
    if lookback is None:
        lookback = DEFAULT_LOOKBACK_DAYS
    try:
        lookback_days = int(lookback)
    except (TypeError, ValueError) as exc:
        raise ValueError("lookback_days 必须是正整数") from exc
    if lookback_days < 1:
        raise ValueError("lookback_days 必须是正整数")

    min_price = _optional_non_negative(raw.get("min_price"), "min_price")
    min_adv = _optional_non_negative(raw.get("min_adv_usd"), "min_adv_usd")
    if min_price is None and min_adv is None:
        raise ValueError("至少指定 min_price 或 min_adv_usd")
    return UniverseRuleSet(min_price=min_price, min_adv_usd=min_adv, lookback_days=lookback_days)


def _optional_non_negative(value: object, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{name} 必须是非负数")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须是非负数") from exc
    if number < 0:
        raise ValueError(f"{name} 必须是非负数")
    return number


def passing_mask(frame: pd.DataFrame, rules: UniverseRuleSet) -> tuple[list[date], list[bool]]:
    """Per trading-day pass/fail aligned to the frame (no invented bars)."""
    if frame.empty:
        return [], []
    df = frame.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp")
    close = df["close"].astype(float)
    volume = df["volume"].astype(float)
    dollar = close * volume
    adv = dollar.rolling(window=rules.lookback_days, min_periods=rules.lookback_days).mean()
    mask = pd.Series(True, index=df.index)
    if rules.min_price is not None:
        mask &= close >= rules.min_price
    if rules.min_adv_usd is not None:
        mask &= adv >= rules.min_adv_usd
    mask &= adv.notna()
    dates: list[date] = []
    for ts in df["timestamp"]:
        dates.append(ts.date() if hasattr(ts, "date") else date.fromisoformat(str(ts)[:10]))
    return dates, mask.tolist()


def passing_dates(frame: pd.DataFrame, rules: UniverseRuleSet) -> list[date]:
    dates, flags = passing_mask(frame, rules)
    return [day for day, ok in zip(dates, flags) if ok]


def memberships_from_mask(symbol: str, dates: list[date], passed: list[bool]) -> list[Membership]:
    if not dates:
        return []
    if len(dates) != len(passed):
        raise ValueError("dates 与 passed 长度不一致")
    last_bar = dates[-1]
    runs: list[tuple[date, date]] = []
    start: date | None = None
    end: date | None = None
    for day, ok in zip(dates, passed):
        if ok:
            if start is None:
                start = day
            end = day
        elif start is not None and end is not None:
            runs.append((start, end))
            start = None
            end = None
    if start is not None and end is not None:
        runs.append((start, end))
    members = [
        Membership(
            symbol=symbol,
            effective_from=begin,
            effective_to=None if close == last_bar else close,
        )
        for begin, close in runs
    ]
    validate_memberships(members)
    return members


def evaluate_symbol(frame: pd.DataFrame, symbol: str, rules: UniverseRuleSet) -> list[Membership]:
    dates, flags = passing_mask(frame, rules)
    return memberships_from_mask(symbol, dates, flags)


def evaluate_universe(frames: dict[str, pd.DataFrame], rules: UniverseRuleSet) -> list[Membership]:
    members: list[Membership] = []
    for symbol in frames:
        members.extend(evaluate_symbol(frames[symbol], symbol, rules))
    validate_memberships(members)
    return members


def rules_summary(rules: UniverseRuleSet | dict[str, Any] | None) -> str:
    parsed = rules if isinstance(rules, UniverseRuleSet) else parse_rules(rules)
    parts: list[str] = []
    if parsed.min_price is not None:
        parts.append(f"min_price {parsed.min_price:g}")
    if parsed.min_adv_usd is not None:
        parts.append(f"min_adv_usd {parsed.min_adv_usd:g}")
    parts.append(f"lookback {parsed.lookback_days}d")
    return " · ".join(parts)
