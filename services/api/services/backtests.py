from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.models import (
    AuditLog,
    Backtest,
    BacktestEquity,
    BacktestMetrics,
    BacktestMonthlyReturn,
    BacktestStatus,
    BacktestTrade,
    Strategy,
    StrategyVersion,
)
from services.api.schemas import BacktestCreate, BacktestOut
from services.api.services.strategies import get_version


def list_backtests(db: Session) -> list[Backtest]:
    return list(db.scalars(select(Backtest).order_by(Backtest.created_at.desc())).all())


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
        }
    )


def create_backtest(db: Session, payload: BacktestCreate) -> Backtest:
    from pathlib import Path

    from quant.data.ingest_spy import data_status
    from quant.engine.lean import LeanQuantEngine
    from services.api.settings import get_settings

    version = get_version(db, payload.strategy_version_id)
    if payload.end_date <= payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="结束日期必须晚于开始日期",
        )

    settings = get_settings()
    market = data_status(Path(settings.data_root))
    if not market.get("ready"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="还没有 SPY 行情数据。请打开「设置」点击「拉取 SPY 行情」。",
        )

    lean_health = LeanQuantEngine(
        lean_image=settings.lean_image,
        data_root=Path(settings.data_root),
        jobs_root=Path(settings.jobs_root),
    ).health_check()
    if not lean_health.get("docker_available"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "需要 Docker（Colima）才能跑 LEAN 回测。"
                "请先执行 colima start，并用 DOCKER_HOST 重启 API。行情数据已经就绪。"
            ),
        )

    backtest = Backtest(
        strategy_version_id=version.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        benchmark=payload.benchmark,
        initial_capital=payload.initial_capital,
        parameters=payload.parameters,
        status=BacktestStatus.QUEUED,
        progress_step="Queued",
    )
    db.add(backtest)
    db.add(
        AuditLog(
            actor="local",
            action="Backtest Started",
            object_type="backtest",
            object_id="pending",
            after={
                "strategy_version_id": str(version.id),
                "start_date": str(payload.start_date),
                "end_date": str(payload.end_date),
            },
        )
    )
    db.commit()
    db.refresh(backtest)

    # Fix audit object id now that we have UUID
    audit = db.scalars(
        select(AuditLog)
        .where(AuditLog.object_type == "backtest", AuditLog.object_id == "pending")
        .order_by(AuditLog.id.desc())
        .limit(1)
    ).first()
    if audit:
        audit.object_id = str(backtest.id)
        db.commit()

    import threading

    from services.worker.tasks import execute_backtest

    bt_id = str(backtest.id)
    threading.Thread(
        target=execute_backtest, args=(bt_id,), daemon=True, name=f"backtest-{bt_id}"
    ).start()
    return backtest


def cancel_backtest(db: Session, backtest_id: UUID) -> Backtest:
    backtest = get_backtest(db, backtest_id)
    if backtest.status in {
        BacktestStatus.COMPLETED,
        BacktestStatus.FAILED,
        BacktestStatus.CANCELLED,
    }:
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
    return backtest


def get_metrics(db: Session, backtest_id: UUID) -> BacktestMetrics:
    get_backtest(db, backtest_id)
    metrics = db.get(BacktestMetrics, backtest_id)
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指标尚未生成")
    return metrics


def get_equity(db: Session, backtest_id: UUID) -> list[BacktestEquity]:
    get_backtest(db, backtest_id)
    return list(
        db.scalars(
            select(BacktestEquity)
            .where(BacktestEquity.backtest_id == backtest_id)
            .order_by(BacktestEquity.ts.asc())
        ).all()
    )


def get_trades(db: Session, backtest_id: UUID) -> list[BacktestTrade]:
    get_backtest(db, backtest_id)
    return list(
        db.scalars(
            select(BacktestTrade)
            .where(BacktestTrade.backtest_id == backtest_id)
            .order_by(BacktestTrade.trade_date.asc())
        ).all()
    )


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
    equity = get_equity(db, backtest_id)
    return [
        {
            "ts": point.ts,
            "drawdown": point.drawdown,
            "strategy_value": point.strategy_value,
        }
        for point in equity
    ]
