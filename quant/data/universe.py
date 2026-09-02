from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from quant.data.quality import STALE_CALENDAR_DAYS
from quant.data.symbols import normalize_symbols

# Inclusive last day used in LEAN map files when membership has no end.
LEAN_OPEN_ENDED = date(2050, 12, 31)


@dataclass(frozen=True)
class Membership:
    """Point-in-time universe membership. Dates are inclusive on both ends."""

    symbol: str
    effective_from: date
    effective_to: date | None = None

    def contains(self, on: date) -> bool:
        if on < self.effective_from:
            return False
        if self.effective_to is not None and on > self.effective_to:
            return False
        return True

    def overlaps(self, start: date, end: date) -> bool:
        if end < start:
            raise ValueError("区间结束日必须不早于开始日")
        last = self.effective_to or date.max
        return self.effective_from <= end and last >= start

    def to_dict(self) -> dict[str, str | None]:
        return {
            "symbol": self.symbol,
            "effective_from": self.effective_from.isoformat(),
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Membership:
        symbol = normalize_symbols([str(payload["symbol"])])[0]
        raw_to = payload.get("effective_to")
        return cls(
            symbol=symbol,
            effective_from=_as_date(payload["effective_from"]),
            effective_to=_as_date(raw_to) if raw_to else None,
        )


def _as_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def validate_memberships(members: Iterable[Membership]) -> None:
    rows = list(members)
    by_symbol: dict[str, list[Membership]] = {}
    for member in rows:
        if member.effective_to is not None and member.effective_to < member.effective_from:
            raise ValueError(
                f"{member.symbol} 的 effective_to ({member.effective_to}) 早于 effective_from"
            )
        by_symbol.setdefault(member.symbol, []).append(member)
    for symbol, group in by_symbol.items():
        ordered = sorted(group, key=lambda m: m.effective_from)
        prev: Membership | None = None
        for current in ordered:
            if prev is None:
                prev = current
                continue
            prev_last = prev.effective_to or date.max
            if current.effective_from <= prev_last:
                raise ValueError(f"{symbol} 的成分区间重叠，拒绝写入（生存者偏差会因此被掩盖）")
            prev = current


def constituents_as_of(members: Iterable[Membership], on: date) -> list[str]:
    seen: list[str] = []
    for member in members:
        if member.contains(on) and member.symbol not in seen:
            seen.append(member.symbol)
    return seen


def memberships_overlapping(
    members: Iterable[Membership], start: date, end: date
) -> list[Membership]:
    return [member for member in members if member.overlaps(start, end)]


def constituents_overlapping(members: Iterable[Membership], start: date, end: date) -> list[str]:
    seen: list[str] = []
    for member in memberships_overlapping(members, start, end):
        if member.symbol not in seen:
            seen.append(member.symbol)
    return seen


def lean_map_file_text(member: Membership) -> str:
    lower = member.symbol.lower()
    start = member.effective_from.strftime("%Y%m%d")
    end = (member.effective_to or LEAN_OPEN_ENDED).strftime("%Y%m%d")
    return f"{start},{lower}\n{end},{lower}\n"


def write_lean_map_files(map_dir: Path, memberships: Iterable[Membership]) -> None:
    """Write per-symbol LEAN map files. Overwrites files in map_dir only (job overlay)."""
    map_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[Membership]] = {}
    for member in memberships:
        grouped.setdefault(member.symbol, []).append(member)
    for symbol, group in grouped.items():
        chunks = [
            lean_map_file_text(item).rstrip("\n")
            for item in sorted(group, key=lambda m: m.effective_from)
        ]
        (map_dir / f"{symbol.lower()}.csv").write_text("\n".join(chunks) + "\n", encoding="utf-8")


def infer_effective_to_from_bars(last_bar: date, *, as_of: date | None = None) -> date | None:
    """If the last bar is stale, treat last_bar as the inclusive delist/exit date."""
    today = as_of or date.today()
    age = (today - last_bar).days
    if age > STALE_CALENDAR_DAYS:
        return last_bar
    return None


def inferred_delistings(
    last_bars: dict[str, date], *, as_of: date | None = None
) -> list[dict[str, str]]:
    """Map stale last-bars to inclusive effective_to. Live names are omitted."""
    rows: list[dict[str, str]] = []
    for symbol, last_bar in last_bars.items():
        inferred = infer_effective_to_from_bars(last_bar, as_of=as_of)
        if inferred is None:
            continue
        rows.append(
            {
                "symbol": symbol,
                "last_bar": last_bar.isoformat(),
                "effective_to": inferred.isoformat(),
            }
        )
    return rows
