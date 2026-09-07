"""Resolve a strategy version's optional ``risk_limits`` block for a backtest.

Returns ``None`` when no binding limit is configured (the run stays a pure
pass-through, byte-identical to today). Raises ``ValueError`` on a malformed
block so the worker fails the run loudly before it ever reaches LEAN.
"""

from __future__ import annotations

import json
from typing import Any

from quant.risk.limits import parse_risk_limits


def resolve_risk_config_json(version_config: Any) -> str | None:
    if not isinstance(version_config, dict):
        return None
    block = version_config.get("risk_limits")
    if not block:
        return None
    limits = parse_risk_limits(block)
    if not limits.can_alter_order():
        return None
    return json.dumps(limits.to_dict())
