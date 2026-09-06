"""Celery task package (formerly a single ``services/worker/tasks.py`` module).

Split into domain modules so no file runs to ~1,300 lines:

- ``backtests`` — backtest execution, cancellation, orphan reconciliation
- ``scans`` — shared scan/validation-run machinery
- ``validation`` — walk-forward / PBO / sensitivity / cost (LEAN-scanning kinds)
- ``validation_post`` — bootstrap / regime / SPA (post-hoc, no LEAN)
- ``data`` — symbol ingest and market reconcile

This ``__init__`` keeps the historical import surface intact: API code and unit
tests import ``services.worker.tasks.<name>`` and patch
``services.worker.tasks.<attr>``. Domain modules therefore resolve their
runtime dependencies (``SessionLocal``, ``LeanQuantEngine``, cross-module
callables such as ``execute_backtest``) through this package namespace at call
time, so a ``monkeypatch`` on the package attribute is observed by the running
task.
"""

from __future__ import annotations

from quant.engine.lean import LeanQuantEngine
from services.api.db import SessionLocal

from . import backtests, data, validation, validation_post
from ._common import cancel_key, flag_cancel, is_cancel_flagged, log

# Backtest domain
reconcile_orphan_backtests = backtests.reconcile_orphan_backtests
reconcile_orphan_backtests_task = backtests.reconcile_orphan_backtests_task
execute_backtest = backtests.execute_backtest
run_backtest_task = backtests.run_backtest_task

# Validation kinds (LEAN-scanning)
execute_walk_forward = validation.execute_walk_forward
run_walk_forward_task = validation.run_walk_forward_task  # type: ignore[has-type]
execute_pbo_scan = validation.execute_pbo_scan
run_pbo_scan_task = validation.run_pbo_scan_task  # type: ignore[has-type]
execute_sensitivity_scan = validation.execute_sensitivity_scan
run_sensitivity_scan_task = validation.run_sensitivity_scan_task  # type: ignore[has-type]
execute_cost_scan = validation.execute_cost_scan
run_cost_scan_task = validation.run_cost_scan_task  # type: ignore[has-type]

# Validation kinds (post-hoc)
execute_bootstrap = validation_post.execute_bootstrap
run_bootstrap_task = validation_post.run_bootstrap_task  # type: ignore[has-type]
execute_regime = validation_post.execute_regime
run_regime_task = validation_post.run_regime_task  # type: ignore[has-type]
execute_spa = validation_post.execute_spa
run_spa_task = validation_post.run_spa_task  # type: ignore[has-type]

# Data domain
run_ingest_task = data.run_ingest_task
reconcile_market_data_task = data.reconcile_market_data_task

__all__ = [
    "SessionLocal",
    "LeanQuantEngine",
    "flag_cancel",
    "cancel_key",
    "is_cancel_flagged",
    "log",
    "reconcile_orphan_backtests",
    "reconcile_orphan_backtests_task",
    "execute_backtest",
    "run_backtest_task",
    "execute_walk_forward",
    "run_walk_forward_task",
    "execute_pbo_scan",
    "run_pbo_scan_task",
    "execute_sensitivity_scan",
    "run_sensitivity_scan_task",
    "execute_cost_scan",
    "run_cost_scan_task",
    "execute_bootstrap",
    "run_bootstrap_task",
    "execute_regime",
    "run_regime_task",
    "execute_spa",
    "run_spa_task",
    "run_ingest_task",
    "reconcile_market_data_task",
]
