from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from quant.data.ingest_spy import data_status, load_symbol_parquet
from quant.data.quality import validate_ohlcv
from quant.data.symbols import as_symbol_list, normalize_symbols
from quant.data.universe import Membership
from services.api.hashing import canonical_hash
from services.api.models import (
    AuditLog,
    Backtest,
    BacktestEquity,
    BacktestMetrics,
    BacktestMonthlyReturn,
    BacktestRollingWindow,
    BacktestStatus,
    BacktestTimeSeries,
    BacktestTrade,
    ExperimentTrial,
    Strategy,
    StrategyVersion,
)
from services.api.schemas import BacktestCreate, BacktestOut
from services.api.services import snapshots as snapshot_service
from services.api.services import universes as universe_service
from services.api.services.backtest_cache import find_cached_backtest, result_fingerprint
from services.api.services.strategies import get_version
from services.api.settings import get_settings

_TERMINAL = {BacktestStatus.COMPLETED, BacktestStatus.FAILED, BacktestStatus.CANCELLED}


def list_backtests(
    db: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    strategy_id: UUID | None = None,
    status_filter: BacktestStatus | None = None,
    start_from: date | None = None,
    end_to: date | None = None,
) -> tuple[list[Backtest], int]:
    stmt = select(Backtest)
    count_stmt = select(func.count()).select_from(Backtest)
    if strategy_id is not None:
        stmt = stmt.join(StrategyVersion).where(StrategyVersion.strategy_id == strategy_id)
        count_stmt = count_stmt.join(StrategyVersion).where(
            StrategyVersion.strategy_id == strategy_id
        )
    if status_filter is not None:
        stmt = stmt.where(Backtest.status == status_filter)
        count_stmt = count_stmt.where(Backtest.status == status_filter)
    if start_from is not None:
        stmt = stmt.where(Backtest.start_date >= start_from)
        count_stmt = count_stmt.where(Backtest.start_date >= start_from)
    if end_to is not None:
        stmt = stmt.where(Backtest.end_date <= end_to)
        count_stmt = count_stmt.where(Backtest.end_date <= end_to)
    total = int(db.scalar(count_stmt) or 0)
    rows = list(
        db.scalars(stmt.order_by(Backtest.created_at.desc()).offset(offset).limit(limit)).all()
    )
    return rows, total


def get_backtest(db: Session, backtest_id: UUID) -> Backtest:
    backtest = db.get(Backtest, backtest_id)
    if not backtest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回测不存在")
    return backtest


def to_out(db: Session, backtest: Backtest) -> BacktestOut:
    version = db.get(StrategyVersion, backtest.strategy_version_id)
    strategy = db.get(Strategy, version.strategy_id) if version else None
    metrics = db.get(BacktestMetrics, backtest.id)
    payload = BacktestOut.model_validate(backtest)
    return payload.model_copy(
        update={
            "strategy_id": strategy.id if strategy else None,
            "strategy_name": strategy.name if strategy else None,
            "version_number": version.version if version else None,
            "total_return": metrics.total_return if metrics else None,
            "sharpe": metrics.sharpe if metrics else None,
            "max_drawdown": metrics.max_drawdown if metrics else None,
            "trade_count": int(metrics.trade_count)
            if metrics and metrics.trade_count is not None
            else None,
            "final_equity": metrics.final_equity if metrics else None,
            "data_snapshot_id": backtest.data_snapshot_id,
            "universe_id": backtest.universe_id,
            "universe_snapshot": backtest.universe_snapshot,
            "result_fingerprint": backtest.result_fingerprint,
            "cache_hit": bool(getattr(backtest, "cache_hit", False)),
        }
    )


def _open_membership_snapshot(symbols: list[str], start: date) -> list[dict]:
    return [
        Membership(symbol=symbol, effective_from=start, effective_to=None).to_dict()
        for symbol in symbols
    ]


def _quality_gate(data_root: Path, symbols: list[str] | None = None) -> None:
    if not symbols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="回测没有标的，无法做质量门禁",
        )
    tickers = symbols
    for symbol in tickers:
        try:
            frame = load_symbol_parquet(data_root, symbol)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"还没有 {symbol} 行情数据。请打开「设置」拉取对应标的。",
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        report = validate_ohlcv(frame)
        if report.has_blocking_issues:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "data_quality",
                    "message": f"{symbol} 行情数据质量校验未通过，拒绝开跑回测。",
                    "report": report.to_dict(),
                },
            )


def _enqueue(backtest_id: str) -> None:
    settings = get_settings()
    if settings.sync_backtests:
        from services.worker.tasks import execute_backtest

        execute_backtest(backtest_id)
        return
    from services.worker.tasks import run_backtest_task

    run_backtest_task.delay(backtest_id)


def create_backtest(db: Session, payload: BacktestCreate) -> Backtest:
    version = get_version(db, payload.strategy_version_id)
    if payload.end_date <= payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="结束日期必须晚于开始日期",
        )

    settings = get_settings()
    host_root = Path(settings.data_root)
    data_root = host_root
    snapshot = None

    if payload.data_snapshot_id is not None:
        snapshot = snapshot_service.get_snapshot(db, payload.data_snapshot_id)
        if snapshot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据快照不存在")
        candidate = host_root / "snapshots" / snapshot.snapshot_key
        if not candidate.exists():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="快照文件已不在磁盘上，无法复现该回测。",
            )
        data_root = candidate
    else:
        market_latest = data_status(host_root)
        if not market_latest.get("ready"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="还没有行情数据。请打开「设置」拉取标的。",
            )
        snapshot = snapshot_service.ensure_snapshot_row(db, host_root)
        if snapshot is not None:
            candidate = host_root / "snapshots" / snapshot.snapshot_key
            if candidate.exists():
                data_root = candidate

    market = data_status(data_root)
    if not market.get("ready"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="还没有行情数据。请打开「设置」拉取标的。",
        )

    if payload.universe_id is not None and payload.universe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="标的池与临时 symbols 不能同时指定",
        )

    universe_snapshot: list[dict] | None = None
    try:
        if payload.universe_id is not None:
            uni = universe_service.get_universe(db, payload.universe_id)
            overlapping = universe_service.resolve_for_range(
                uni, payload.start_date, payload.end_date
            )
            if not overlapping:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="该回测区间内标的池没有成分",
                )
            universe = []
            for member in overlapping:
                if member.symbol not in universe:
                    universe.append(member.symbol)
            universe_snapshot = [member.to_dict() for member in overlapping]
        elif payload.universe:
            universe = normalize_symbols(payload.universe)
            universe_snapshot = _open_membership_snapshot(universe, payload.start_date)
        else:
            raw = market.get("symbols") or (snapshot.symbols if snapshot else None)
            if not raw:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="还没有标的列表。请指定标的池，或打开「设置」拉取行情。",
                )
            universe = as_symbol_list(raw)
            universe_snapshot = _open_membership_snapshot(universe, payload.start_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    _quality_gate(data_root, symbols=universe)

    if market.get("corporate_actions_verified") is False:
        source = (market.get("manifest") or {}).get("source") or "unknown"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "provider_capability",
                "message": f"数据源 {source} 不提供分红数据，无法进行调整价回测。",
            },
        )

    from services.api.services.validation import count_inflight_engine_jobs

    if snapshot is None:
        snapshot = snapshot_service.ensure_snapshot_row(db, data_root)

    fingerprint = result_fingerprint(
        code=version.code,
        data_snapshot_id=snapshot.id if snapshot else None,
        engine_version=settings.lean_image,
        start_date=payload.start_date,
        end_date=payload.end_date,
        benchmark=payload.benchmark,
        initial_capital=payload.initial_capital,
        universe=universe,
        universe_id=payload.universe_id,
        parameters=payload.parameters or {},
    )
    if not payload.force:
        cached = find_cached_backtest(db, fingerprint)
        if cached is not None:
            cached.cache_hit = True  # type: ignore[attr-defined]
            return cached

    if count_inflight_engine_jobs(db) >= settings.max_inflight_backtests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="并发回测已达上限，请等待正在运行的任务完成后再提交。",
        )

    strategy = db.get(Strategy, version.strategy_id)
    params = payload.parameters or {}
    backtest = Backtest(
        strategy_version_id=version.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        benchmark=payload.benchmark,
        initial_capital=payload.initial_capital,
        parameters=params,
        status=BacktestStatus.QUEUED,
        progress_step="Queued",
        data_snapshot_id=snapshot.id if snapshot else None,
        data_version=(snapshot.content_sha256 if snapshot else None)
        or (market.get("manifest") or {}).get("sha256"),
        universe_id=payload.universe_id,
        universe_snapshot=universe_snapshot,
        result_fingerprint=fingerprint,
    )
    db.add(backtest)
    db.flush()
    db.add(
        ExperimentTrial(
            backtest_id=backtest.id,
            data_snapshot_id=snapshot.id if snapshot else None,
            strategy_id=strategy.id if strategy else None,
            universe_key=",".join(universe),
            strategy_family=strategy.family_id if strategy else None,
            parameters=params,
            parameter_hash=canonical_hash(
                {
                    "strategy_version_id": str(version.id),
                    "start_date": str(payload.start_date),
                    "end_date": str(payload.end_date),
                    "benchmark": payload.benchmark,
                    "initial_capital": payload.initial_capital,
                    "universe": universe,
                    "universe_id": str(payload.universe_id) if payload.universe_id else None,
                    "parameters": params,
                }
            ),
        )
    )
    db.add(
        AuditLog(
            actor="local",
            action="Backtest Started",
            object_type="backtest",
            object_id=str(backtest.id),
            after={
                "strategy_version_id": str(version.id),
                "start_date": str(payload.start_date),
                "end_date": str(payload.end_date),
                "data_snapshot_id": str(snapshot.id) if snapshot else None,
            },
        )
    )
    db.commit()
    db.refresh(backtest)
    _enqueue(str(backtest.id))
    return backtest


def cancel_backtest(db: Session, backtest_id: UUID) -> Backtest:
    backtest = get_backtest(db, backtest_id)
    if backtest.status in _TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"当前状态为 {backtest.status.value}，无法取消",
        )
    backtest.status = BacktestStatus.CANCELLED
    backtest.finished_at = datetime.now(timezone.utc)
    backtest.progress_step = "Cancelled"
    db.add(
        AuditLog(
            actor="local",
            action="Backtest Cancelled",
            object_type="backtest",
            object_id=str(backtest.id),
        )
    )
    db.commit()
    db.refresh(backtest)
    from services.worker.tasks import flag_cancel

    flag_cancel(str(backtest.id))
    return backtest


def get_metrics(db: Session, backtest_id: UUID) -> BacktestMetrics:
    get_backtest(db, backtest_id)
    metrics = db.get(BacktestMetrics, backtest_id)
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指标尚未生成")
    return metrics


def get_equity(
    db: Session, backtest_id: UUID, *, limit: int = 5000, offset: int = 0
) -> tuple[list[BacktestEquity], int]:
    get_backtest(db, backtest_id)
    total = int(
        db.scalar(
            select(func.count())
            .select_from(BacktestEquity)
            .where(BacktestEquity.backtest_id == backtest_id)
        )
        or 0
    )
    rows = list(
        db.scalars(
            select(BacktestEquity)
            .where(BacktestEquity.backtest_id == backtest_id)
            .order_by(BacktestEquity.ts.asc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return rows, total


def get_trades(
    db: Session, backtest_id: UUID, *, limit: int = 500, offset: int = 0
) -> tuple[list[BacktestTrade], int]:
    get_backtest(db, backtest_id)
    total = int(
        db.scalar(
            select(func.count())
            .select_from(BacktestTrade)
            .where(BacktestTrade.backtest_id == backtest_id)
        )
        or 0
    )
    rows = list(
        db.scalars(
            select(BacktestTrade)
            .where(BacktestTrade.backtest_id == backtest_id)
            .order_by(BacktestTrade.trade_date.asc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return rows, total


def get_monthly_returns(db: Session, backtest_id: UUID) -> list[BacktestMonthlyReturn]:
    get_backtest(db, backtest_id)
    return list(
        db.scalars(
            select(BacktestMonthlyReturn)
            .where(BacktestMonthlyReturn.backtest_id == backtest_id)
            .order_by(BacktestMonthlyReturn.year.asc(), BacktestMonthlyReturn.month.asc())
        ).all()
    )


def get_drawdowns(db: Session, backtest_id: UUID) -> list[dict]:
    rows, _ = get_equity(db, backtest_id, limit=50_000, offset=0)
    return [
        {
            "ts": point.ts,
            "drawdown": point.drawdown,
            "strategy_value": point.strategy_value,
        }
        for point in rows
    ]


def get_rolling_windows(db: Session, backtest_id: UUID) -> list[BacktestRollingWindow]:
    get_backtest(db, backtest_id)
    return list(
        db.scalars(
            select(BacktestRollingWindow)
            .where(BacktestRollingWindow.backtest_id == backtest_id)
            .order_by(BacktestRollingWindow.period_end.asc())
        ).all()
    )


def get_time_series(
    db: Session, backtest_id: UUID, name: str | None = None
) -> list[BacktestTimeSeries]:
    get_backtest(db, backtest_id)
    stmt = select(BacktestTimeSeries).where(BacktestTimeSeries.backtest_id == backtest_id)
    if name:
        stmt = stmt.where(BacktestTimeSeries.name == name)
    return list(db.scalars(stmt.order_by(BacktestTimeSeries.ts.asc())).all())


def get_logs(backtest_id: UUID) -> dict[str, str]:
    settings = get_settings()
    job_dir = Path(settings.jobs_root) / str(backtest_id)
    stdout = job_dir / "docker_stdout.log"
    stderr = job_dir / "docker_stderr.log"
    return {
        "stdout": stdout.read_text(encoding="utf-8") if stdout.exists() else "",
        "stderr": stderr.read_text(encoding="utf-8") if stderr.exists() else "",
    }
