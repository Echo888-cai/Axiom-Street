"""Shared leaf helpers for the Celery task package.

Nothing in here imports a sibling task module, so `_common` is always safe to
import first. Task modules resolve runtime dependencies (DB session, LEAN
engine, cross-module callables) through the package namespace so that unit
tests can keep patching ``services.worker.tasks.<name>`` after the split.
"""

from __future__ import annotations

import redis
import structlog

from quant.data.symbols import as_symbol_list
from quant.data.universe import Membership
from services.api.settings import get_settings

log = structlog.get_logger("axiom.worker")

_NO_UNIVERSE = "回测没有标的。请指定标的池、临时 symbols，或先拉取行情。"


def resolve_execution_universe(
    *,
    universe_snapshot: list | None,
    snapshot_symbols: object | None,
    config: object | None,
) -> tuple[list[str], list[Membership]]:
    """PIT snapshot wins. Never guess SPY."""
    memberships: list[Membership] = []
    universe: list[str] = []
    if universe_snapshot:
        memberships = [Membership.from_dict(item) for item in universe_snapshot]
        for member in memberships:
            if member.symbol not in universe:
                universe.append(member.symbol)
        if universe:
            return universe, memberships
    if snapshot_symbols:
        universe = as_symbol_list(snapshot_symbols)
        return universe, memberships
    if isinstance(config, dict):
        configured = (config.get("universe") or {}).get("symbols")
        if configured:
            universe = as_symbol_list(configured)
            return universe, memberships
    raise ValueError(_NO_UNIVERSE)


def _redis():
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def cancel_key(backtest_id: str) -> str:
    return f"axiom:cancel:{backtest_id}"


def flag_cancel(backtest_id: str) -> None:
    try:
        _redis().setex(cancel_key(backtest_id), 3600, "1")
    except redis.RedisError:
        pass


def is_cancel_flagged(backtest_id: str) -> bool:
    try:
        return bool(_redis().get(cancel_key(backtest_id)))
    except redis.RedisError:
        return False


def _set_progress(db, backtest, status, step: str) -> None:
    backtest.status = status
    backtest.progress_step = step
    db.commit()


def _validation_step_count(params: dict | None) -> int:
    payload = params or {}
    for key in ("folds", "values", "costs_bps"):
        items = payload.get(key) or []
        if isinstance(items, list) and items:
            return max(len(items), 1)
    return 1
