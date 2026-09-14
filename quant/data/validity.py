"""P3.2 point-in-time validity: never let "unknown validity" pass as if it were
a verified historical membership.

A universe can arrive in three shapes:

- ``point_in_time`` — memberships with ``effective_from``/``effective_to``: the
  historical composition is known and LEAN map files enforce it.
- ``snapshot`` — a symbol list captured with the data snapshot but without
  有效日期: composition validity is **unknown**; using it for a historical
  backtest can silently back-fill today's constituents.
- ``config`` — symbols hard-coded in the strategy config: same unknown validity.

The UI must state which one applies before a run, so a reader never mistakes an
unknown-validity universe for a point-in-time one.
"""

from __future__ import annotations

from datetime import date
from typing import Any

STATUS_POINT_IN_TIME = "point_in_time"
STATUS_SNAPSHOT = "snapshot"
STATUS_CONFIG = "config"

UNKNOWN_VALIDITY_NOTE = (
    "标的池未携带有效期：历史成分可能被当前成分回填，结论不适用于当时可交易集合。"
)


def classify_universe_validity(
    memberships: list[Any] | None,
    universe: list[str] | None,
    *,
    source: str = "config",
) -> dict[str, Any]:
    """Classify a run's universe and state its validity explicitly."""
    members = list(memberships or [])
    symbols = list(universe or [])
    if members:
        starts = [m.effective_from for m in members if getattr(m, "effective_from", None)]
        ends = [m.effective_to for m in members if getattr(m, "effective_to", None)]
        return {
            "status": STATUS_POINT_IN_TIME,
            "known": True,
            "symbols": symbols or sorted({m.symbol for m in members}),
            "effective_from": min(starts).isoformat() if starts else None,
            "effective_to": max(ends).isoformat() if ends else None,
            "note": "标的池携带有效期，回归按当时成分执行（LEAN map files 生效）。",
        }
    if symbols:
        return {
            "status": STATUS_SNAPSHOT if source == "snapshot" else STATUS_CONFIG,
            "known": False,
            "symbols": symbols,
            "effective_from": None,
            "effective_to": None,
            "note": UNKNOWN_VALIDITY_NOTE,
        }
    return {
        "status": STATUS_CONFIG,
        "known": False,
        "symbols": [],
        "effective_from": None,
        "effective_to": None,
        "note": "未指定标的池：运行会在执行前被拒绝。",
    }


def membership_valid_on(memberships: list[Any], day: date) -> list[str]:
    """Symbols actually tradable on ``day`` (point-in-time filter)."""
    return [m.symbol for m in memberships if m.contains(day)]
