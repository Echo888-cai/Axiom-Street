"""Point-in-time universe filters evaluated on ingested bars and fundamentals.

Price and ADV come from the snapshot so a RULE universe cannot invent
constituents that were never in the data. Market cap is shares(as-of) × close.
Sector/industry apply only on/after the classification as-of date — never
retroactively. Missing fundamentals fail loud; they are not skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from quant.data.fundamentals import Fundamentals
from quant.data.universe import Membership, validate_memberships

ALLOWED_RULE_KEYS = frozenset(
    {
        "min_price",
        "min_adv_usd",
        "lookback_days",
        "min_market_cap_usd",
        "sectors",
        "industries",
    }
)
DEFAULT_LOOKBACK_DAYS = 21


@dataclass(frozen=True)
class UniverseRuleSet:
    min_price: float | None = None
    min_adv_usd: float | None = None
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    min_market_cap_usd: float | None = None
    sectors: tuple[str, ...] = field(default_factory=tuple)
    industries: tuple[str, ...] = field(default_factory=tuple)

    @property
    def needs_shares(self) -> bool:
        return self.min_market_cap_usd is not None

    @property
    def needs_classification(self) -> bool:
        return bool(self.sectors or self.industries)

    @property
    def needs_fundamentals(self) -> bool:
        return self.needs_shares or self.needs_classification

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"lookback_days": self.lookback_days}
        if self.min_price is not None:
            payload["min_price"] = self.min_price
        if self.min_adv_usd is not None:
            payload["min_adv_usd"] = self.min_adv_usd
        if self.min_market_cap_usd is not None:
            payload["min_market_cap_usd"] = self.min_market_cap_usd
        if self.sectors:
            payload["sectors"] = list(self.sectors)
        if self.industries:
            payload["industries"] = list(self.industries)
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
    min_cap = _optional_non_negative(raw.get("min_market_cap_usd"), "min_market_cap_usd")
    sectors = _name_list(raw.get("sectors"), "sectors")
    industries = _name_list(raw.get("industries"), "industries")
    if min_price is None and min_adv is None and min_cap is None and not sectors and not industries:
        raise ValueError(
            "至少指定 min_price、min_adv_usd、min_market_cap_usd、sectors 或 industries"
        )
    return UniverseRuleSet(
        min_price=min_price,
        min_adv_usd=min_adv,
        lookback_days=lookback_days,
        min_market_cap_usd=min_cap,
        sectors=sectors,
        industries=industries,
    )


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


def _name_list(value: object, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raise ValueError(f"{name} 必须是字符串列表，不能是单个字符串")
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} 必须是字符串列表")
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{name} 的每一项必须是非空字符串")
        label = item.strip()
        key = label.casefold()
        if key not in seen:
            seen.add(key)
            out.append(label)
    if not out:
        raise ValueError(f"{name} 不能为空列表")
    return tuple(out)


def passing_mask(
    frame: pd.DataFrame,
    rules: UniverseRuleSet,
    fundamentals: Fundamentals | None = None,
    *,
    symbol: str = "",
) -> tuple[list[date], list[bool]]:
    """Per trading-day pass/fail aligned to the frame (no invented bars)."""
    if frame.empty:
        return [], []
    _require_fundamentals(symbol, rules, fundamentals)
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
    if rules.min_market_cap_usd is not None:
        assert fundamentals is not None
        caps = [_market_cap(fundamentals, day, price) for day, price in zip(dates, close.tolist())]
        cap_ok = [(c is not None and c >= rules.min_market_cap_usd) for c in caps]
        mask &= pd.Series(cap_ok, index=df.index)
    if rules.sectors or rules.industries:
        assert fundamentals is not None
        class_ok = [_classification_ok(fundamentals, day, rules) for day in dates]
        mask &= pd.Series(class_ok, index=df.index)
    return dates, mask.tolist()


def _require_fundamentals(
    symbol: str, rules: UniverseRuleSet, fundamentals: Fundamentals | None
) -> None:
    label = symbol or "该标的"
    if rules.needs_shares:
        if fundamentals is None or not fundamentals.has_shares():
            raise ValueError(
                f"{label} 缺少时点股本，无法计算市值。"
                "拒绝用当前市值回填历史。请先摄取基本面后再重建。"
            )
    if rules.needs_classification:
        if fundamentals is None or not fundamentals.has_classification():
            raise ValueError(
                f"{label} 缺少行业/板块分类。"
                "拒绝用未标注的标的默认为未入选。请先摄取基本面后再重建。"
            )
        if rules.sectors and not fundamentals.sector:
            raise ValueError(
                f"{label} 没有 sector 字段（当前源只提供 industry/SIC）。"
                "不要把 SIC 近似成 GICS 板块；请改用 industries 或更换基本面源。"
            )
        if rules.industries and not fundamentals.industry:
            raise ValueError(f"{label} 没有 industry 字段，无法做行业筛选")


def _market_cap(fundamentals: Fundamentals, day: date, close: float) -> float | None:
    shares = fundamentals.shares_as_of(day)
    if shares is None:
        return None
    return shares * float(close)


def _classification_ok(fundamentals: Fundamentals, day: date, rules: UniverseRuleSet) -> bool:
    if not fundamentals.classification_known_on(day):
        return False
    if rules.sectors:
        sector = (fundamentals.sector or "").casefold()
        allowed = {item.casefold() for item in rules.sectors}
        if sector not in allowed:
            return False
    if rules.industries:
        industry = (fundamentals.industry or "").casefold()
        allowed = {item.casefold() for item in rules.industries}
        if industry not in allowed:
            return False
    return True


def passing_dates(
    frame: pd.DataFrame,
    rules: UniverseRuleSet,
    fundamentals: Fundamentals | None = None,
    *,
    symbol: str = "",
) -> list[date]:
    dates, flags = passing_mask(frame, rules, fundamentals, symbol=symbol)
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


def evaluate_symbol(
    frame: pd.DataFrame,
    symbol: str,
    rules: UniverseRuleSet,
    fundamentals: Fundamentals | None = None,
) -> list[Membership]:
    dates, flags = passing_mask(frame, rules, fundamentals, symbol=symbol)
    return memberships_from_mask(symbol, dates, flags)


def evaluate_universe(
    frames: dict[str, pd.DataFrame],
    rules: UniverseRuleSet,
    fundamentals: dict[str, Fundamentals] | None = None,
) -> list[Membership]:
    fund_map = fundamentals or {}
    problems: list[str] = []
    for symbol in frames:
        try:
            _require_fundamentals(symbol, rules, fund_map.get(symbol))
        except ValueError as exc:
            problems.append(str(exc))
    if problems:
        raise ValueError(
            "以下标的缺少规则所需的时点基本面，拒绝重建（不会把缺失标的静默踢出池外）。 "
            + " ".join(problems)
        )
    members: list[Membership] = []
    for symbol in frames:
        members.extend(evaluate_symbol(frames[symbol], symbol, rules, fund_map.get(symbol)))
    validate_memberships(members)
    return members


def rules_summary(rules: UniverseRuleSet | dict[str, Any] | None) -> str:
    parsed = rules if isinstance(rules, UniverseRuleSet) else parse_rules(rules)
    parts: list[str] = []
    if parsed.min_price is not None:
        parts.append(f"min_price {parsed.min_price:g}")
    if parsed.min_adv_usd is not None:
        parts.append(f"min_adv_usd {parsed.min_adv_usd:g}")
    if parsed.min_market_cap_usd is not None:
        parts.append(f"min_market_cap_usd {parsed.min_market_cap_usd:g}")
    if parsed.sectors:
        parts.append("sectors " + "/".join(parsed.sectors))
    if parsed.industries:
        parts.append("industries " + "/".join(parsed.industries))
    parts.append(f"lookback {parsed.lookback_days}d")
    return " · ".join(parts)
