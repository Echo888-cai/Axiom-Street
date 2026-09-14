"""Versioned rules schema for the strategy builder (P2.1).

The guided builder produces a structured ``config`` (rules) plus deterministic
code.  To keep "规则、代码、版本" stable across UI iterations:

- ``BUILDER_SCHEMA_VERSION`` versions the rules shape; a config claiming a
  future version is rejected instead of silently downgraded.
- ``normalize_builder_config`` validates the guided trend rules ranges on the
  server, so non-builder configs and out-of-range rule edits are refused at the
  contract boundary (HTTP 422), not discovered later in a backtest.
- ``strategy_code_hash`` gives both client and server a shared digest for
  stale-draft conflict detection (P2.1 acceptance: 过期草稿不能覆盖新版本).
"""

from __future__ import annotations

import hashlib
from typing import Any

BUILDER_SCHEMA_VERSION = 1

_LOOKBACK_MIN, _LOOKBACK_MAX = 20, 500
_POSITION_PCT_MIN, _POSITION_PCT_MAX = 1, 100
_SLIPPAGE_BPS_MIN, _SLIPPAGE_BPS_MAX = 0, 100

_STATUS_EMPTY = ("", None)


def strategy_code_hash(code: str) -> str:
    """Stable sha256 hex of strategy source; shared with the web client."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _require_bounded(value: Any, low: int | float, high: int | float, label: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label}必须是数字（{low}–{high}）")
    if float(value) < low or float(value) > high:
        raise ValueError(f"{label}超出允许范围（{low}–{high}）")


def normalize_builder_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """Return a schema-versioned copy of a builder config, or raise ValueError.

    Trend-shaped configs (``signal.lookback_period`` set) are validated against
    the guided builder limits; equal-weight and custom configs pass through with
    only the schema/version guard.
    """
    cfg = dict(config or {})
    version = cfg.get("schema_version", BUILDER_SCHEMA_VERSION)
    if (
        not isinstance(version, int)
        or isinstance(version, bool)
        or version > BUILDER_SCHEMA_VERSION
    ):
        raise ValueError(
            f"规则 schema 版本 {version!r} 高于当前支持版本 {BUILDER_SCHEMA_VERSION}，请升级工作台后重试。"
        )
    cfg.setdefault("schema_version", BUILDER_SCHEMA_VERSION)

    signal = cfg.get("signal") or {}
    lookback = signal.get("lookback_period")
    if lookback not in _STATUS_EMPTY:
        _require_bounded(lookback, _LOOKBACK_MIN, _LOOKBACK_MAX, "均线周期（交易日）")

    sizing = cfg.get("position_sizing") or {}
    target_weight = sizing.get("target_weight")
    if target_weight is not None and target_weight != "":
        pct = float(target_weight) * 100
        _require_bounded(pct, _POSITION_PCT_MIN, _POSITION_PCT_MAX, "持仓比例（%）")

    execution = cfg.get("execution") or {}
    slippage = execution.get("slippage_bps")
    if slippage not in _STATUS_EMPTY:
        _require_bounded(slippage, _SLIPPAGE_BPS_MIN, _SLIPPAGE_BPS_MAX, "滑点（bps）")

    return cfg
