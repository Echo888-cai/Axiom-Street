from __future__ import annotations


class EngineTimeout(RuntimeError):
    pass


class BacktestCancelled(RuntimeError):
    pass
