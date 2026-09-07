"""Risk engine (Phase 6 WP-1).

Pure, self-contained modules that gate intended target weights against hard
limits — enforced inside LEAN backtests via a generated wrapper subclass
(see ``quant.risk.gate``). Nothing here touches web/service frameworks; the
engine source is rendered verbatim into the LEAN container.
"""

from quant.risk.gate import compose_strategy_code, runtime_files
from quant.risk.limits import parse_risk_limits
from quant.risk.types import RiskLimits

__all__ = [
    "RiskLimits",
    "compose_strategy_code",
    "parse_risk_limits",
    "runtime_files",
]
