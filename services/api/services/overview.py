"""Database-owned workspace totals, independent of paginated collection views."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.models import Backtest, BacktestStatus, Strategy, StrategyStatus
from services.api.schemas import OverviewOut
from services.api.services.backtests import to_out


def get_overview(db: Session) -> OverviewOut:
    counts = dict.fromkeys(StrategyStatus, 0)
    for status, count in db.execute(
        select(Strategy.status, func.count()).group_by(Strategy.status)
    ):
        counts[status] = count
    latest = db.scalar(
        select(Backtest)
        .where(Backtest.status == BacktestStatus.COMPLETED)
        .order_by(
            func.coalesce(Backtest.finished_at, Backtest.created_at).desc(),
            Backtest.created_at.desc(),
            Backtest.id.desc(),
        )
        .limit(1)
    )
    return OverviewOut(
        strategy_count=sum(counts.values()),
        strategy_counts_by_status=counts,
        latest_completed_backtest=to_out(db, latest) if latest else None,
        as_of=datetime.now(timezone.utc),
    )
