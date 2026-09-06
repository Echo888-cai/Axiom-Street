"""Shared machinery for validation scans: job building, parallel scan
execution against the backtest cache, and validation-run lifecycle helpers.

Held apart from the per-kind ``execute_*`` validators so each module stays
under the ~500-line ceiling. Runtime dependencies resolve through the package
namespace (see ``_common`` module docstring).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from services.api.models import (
    Backtest,
    BacktestEquity,
    BacktestStatus,
    ExperimentTrial,
    Strategy,
    StrategyVersion,
    ValidationRun,
    ValidationRunStatus,
)
from services.api.settings import get_settings
from services.worker import tasks as _tasks

from ._common import log


def _fail_walk_forward(db, run: ValidationRun, code: str, message: str) -> dict:
    run.status = ValidationRunStatus.FAILED
    run.passed = False
    run.progress_step = "Failed"
    run.finished_at = datetime.now(timezone.utc)
    run.error = {"code": code, "message": message}
    db.commit()
    return {"status": "FAILED", "error": message}


class _ScanFailed(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _universe_key(members: object) -> str:
    if isinstance(members, list):
        symbols = [
            str(item.get("symbol", ""))
            for item in members
            if isinstance(item, dict) and item.get("symbol")
        ]
        if symbols:
            return ",".join(symbols)
    return "SPY"


def _scan_parallelism() -> int:
    settings = get_settings()
    if settings.sync_backtests:
        return 1
    return max(1, int(settings.scan_parallelism))


def _equity_payload(db, backtest_id) -> list[dict]:
    points = (
        db.query(BacktestEquity)
        .filter(BacktestEquity.backtest_id == backtest_id)
        .order_by(BacktestEquity.ts.asc())
        .all()
    )
    return [{"ts": row.ts, "strategy_value": row.strategy_value} for row in points]


def _run_scan_backtest(
    db,
    *,
    version: StrategyVersion,
    start: date,
    end: date,
    params: dict,
    bt_params: dict,
    snapshot_id: UUID | None,
    hash_extra: dict,
) -> tuple[Backtest, list[dict]]:
    from services.api.hashing import canonical_hash
    from services.api.services.backtest_cache import (
        find_cached_backtest,
        result_fingerprint,
        universe_from_snapshot,
    )

    settings = get_settings()
    universe = universe_from_snapshot(params.get("universe_snapshot") or [])
    fingerprint = result_fingerprint(
        code=version.code,
        data_snapshot_id=snapshot_id,
        engine_version=settings.lean_image,
        start_date=start,
        end_date=end,
        benchmark=str(params.get("benchmark") or "SPY"),
        initial_capital=float(params.get("initial_capital") or 100_000.0),
        universe=universe,
        universe_id=None,
        parameters=dict(bt_params),
    )
    cached = find_cached_backtest(db, fingerprint)
    if cached is not None and cached.status == BacktestStatus.COMPLETED:
        return cached, _equity_payload(db, cached.id)

    strategy = db.get(Strategy, version.strategy_id)
    backtest = Backtest(
        strategy_version_id=version.id,
        start_date=start,
        end_date=end,
        benchmark=str(params.get("benchmark") or "SPY"),
        initial_capital=float(params.get("initial_capital") or 100_000.0),
        parameters=dict(bt_params),
        status=BacktestStatus.QUEUED,
        progress_step="Queued",
        data_snapshot_id=snapshot_id,
        universe_snapshot=params.get("universe_snapshot") or [],
        result_fingerprint=fingerprint,
    )
    db.add(backtest)
    db.flush()
    db.add(
        ExperimentTrial(
            backtest_id=backtest.id,
            data_snapshot_id=snapshot_id,
            strategy_id=version.strategy_id,
            universe_key=_universe_key(params.get("universe_snapshot") or []),
            strategy_family=(strategy.family_id if strategy else version.strategy_id),
            parameters=dict(bt_params),
            parameter_hash=canonical_hash(
                {
                    "strategy_version_id": str(version.id),
                    "start_date": str(start),
                    "end_date": str(end),
                    **hash_extra,
                }
            ),
        )
    )
    db.commit()
    executed = _tasks.execute_backtest(str(backtest.id), record_gates=False)
    if executed.get("status") != "COMPLETED":
        message = executed.get("error") or executed.get("message") or "参数扫描回测失败"
        raise _ScanFailed("scan_backtest_failed", str(message))
    db.expire_all()
    loaded = db.get(Backtest, backtest.id)
    if loaded is None:
        raise _ScanFailed("scan_backtest_failed", "扫描回测写入后无法读取")
    return loaded, _equity_payload(db, loaded.id)


def _run_scan_configs(
    *,
    version_id: UUID,
    start: date,
    end: date,
    params: dict,
    jobs: list[tuple[dict, dict]],
    on_progress,
) -> list[tuple[Backtest, list[dict]]]:
    """Run scan configs, in parallel when the worker pool has spare slots.

    Celery group/chord would deadlock at concurrency=2 if the parent waited
    on children. Threads here share one worker slot and lease LEAN pool slots.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not jobs:
        return []
    workers = min(_scan_parallelism(), len(jobs))

    def _one(bt_params: dict, hash_extra: dict) -> tuple[Backtest, list[dict]]:
        db = _tasks.SessionLocal()
        try:
            version = db.get(StrategyVersion, version_id)
            if version is None:
                raise _ScanFailed("version_missing", "策略版本不存在")
            return _run_scan_backtest(
                db,
                version=version,
                start=start,
                end=end,
                params=params,
                bt_params=bt_params,
                snapshot_id=UUID(str(params["data_snapshot_id"]))
                if params.get("data_snapshot_id")
                else None,
                hash_extra=hash_extra,
            )
        finally:
            db.close()

    if workers == 1:
        out: list[tuple[Backtest, list[dict]]] = []
        for index, (bt_params, hash_extra) in enumerate(jobs):
            on_progress(index, len(jobs), bt_params)
            out.append(_one(bt_params, hash_extra))
        return out

    ordered: list[tuple[Backtest, list[dict]] | None] = [None] * len(jobs)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_one, bt_params, hash_extra): index
            for index, (bt_params, hash_extra) in enumerate(jobs)
        }
        for fut in as_completed(futures):
            index = futures[fut]
            ordered[index] = fut.result()
            on_progress(index, len(jobs), jobs[index][0])
    filled: list[tuple[Backtest, list[dict]]] = []
    for row in ordered:
        if row is None:
            raise _ScanFailed("scan_backtest_failed", "扫描结果不完整")
        filled.append(row)
    return filled


def _finish_validation(
    db, run: ValidationRun, payload: dict, *, passed: bool, log_event: str, **log_fields
) -> dict:
    run.result = payload
    run.passed = passed
    run.error = None
    run.status = ValidationRunStatus.COMPLETED
    run.progress_step = "Completed"
    run.finished_at = datetime.now(timezone.utc)
    db.flush()
    from services.api.services.validation import maybe_apply_validated

    maybe_apply_validated(
        db, strategy_id=run.strategy_id, strategy_version_id=run.strategy_version_id
    )
    db.commit()
    log.info(log_event, passed=passed, **log_fields)
    return {"status": "COMPLETED", "passed": passed, "run_id": str(run.id)}
