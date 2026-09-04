from __future__ import annotations

import re


class EngineTimeout(RuntimeError):
    pass


class BacktestCancelled(RuntimeError):
    pass


_STRATEGY_LINE = re.compile(r'File "[^"]*strategy\.py", line (\d+)')


def strategy_error_location(message: str) -> int | None:
    """Last ``strategy.py`` traceback line, if LEAN/Python pointed at user code."""
    matches = list(_STRATEGY_LINE.finditer(message or ""))
    if not matches:
        return None
    return int(matches[-1].group(1))
