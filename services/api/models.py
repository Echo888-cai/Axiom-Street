from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.api.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _enum(enum_cls, name: str):
    return Enum(
        enum_cls, name=name, native_enum=False, values_callable=lambda x: [e.value for e in x]
    )


class StrategyStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    BACKTESTED = "BACKTESTED"
    VALIDATED = "VALIDATED"
    PAPER = "PAPER"
    APPROVED = "APPROVED"
    LIVE = "LIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"


class BacktestStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[StrategyStatus] = mapped_column(
        _enum(StrategyStatus, "strategy_status"),
        default=StrategyStatus.DRAFT,
        nullable=False,
    )
    asset_class: Mapped[str] = mapped_column(String(64), default="equity")
    benchmark: Mapped[str] = mapped_column(String(32), default="SPY")
    family_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[List[StrategyVersion]] = relationship(back_populates="strategy")


class StrategyVersion(Base):
    __tablename__ = "strategy_versions"
    __table_args__ = (UniqueConstraint("strategy_id", "version", name="uq_strategy_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    commit_message: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(128), default="local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    strategy: Mapped[Strategy] = relationship(back_populates="versions")
    backtests: Mapped[List[Backtest]] = relationship(back_populates="strategy_version")


class Backtest(Base):
    __tablename__ = "backtests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    strategy_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("strategy_versions.id", ondelete="CASCADE"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    benchmark: Mapped[str] = mapped_column(String(32), default="SPY")
    initial_capital: Mapped[float] = mapped_column(Float, default=100_000.0)
    status: Mapped[BacktestStatus] = mapped_column(
        _enum(BacktestStatus, "backtest_status"),
        default=BacktestStatus.QUEUED,
        nullable=False,
    )
    engine_version: Mapped[Optional[str]] = mapped_column(String(128))
    data_version: Mapped[Optional[str]] = mapped_column(String(128))
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    progress_step: Mapped[Optional[str]] = mapped_column(String(128))
    error: Mapped[Optional[dict]] = mapped_column(JSON)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    strategy_version: Mapped[StrategyVersion] = relationship(back_populates="backtests")
    metrics: Mapped[Optional[BacktestMetrics]] = relationship(
        back_populates="backtest", uselist=False
    )
    equity: Mapped[List[BacktestEquity]] = relationship(back_populates="backtest")
    trades: Mapped[List[BacktestTrade]] = relationship(back_populates="backtest")
    monthly_returns: Mapped[List[BacktestMonthlyReturn]] = relationship(back_populates="backtest")
    rolling_windows: Mapped[List[BacktestRollingWindow]] = relationship(back_populates="backtest")
    time_series: Mapped[List[BacktestTimeSeries]] = relationship(back_populates="backtest")
    data_snapshot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("data_snapshots.id", ondelete="SET NULL"), nullable=True, index=True
    )
    universe_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("universes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    universe_snapshot: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)


class BacktestMetrics(Base):
    __tablename__ = "backtest_metrics"

    backtest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("backtests.id", ondelete="CASCADE"), primary_key=True
    )
    total_return: Mapped[Optional[float]] = mapped_column(Float)
    cagr: Mapped[Optional[float]] = mapped_column(Float)
    annualized_return: Mapped[Optional[float]] = mapped_column(Float)
    benchmark_return: Mapped[Optional[float]] = mapped_column(Float)
    excess_return: Mapped[Optional[float]] = mapped_column(Float)
    alpha_capm: Mapped[Optional[float]] = mapped_column(Float)
    beta: Mapped[Optional[float]] = mapped_column(Float)
    information_ratio: Mapped[Optional[float]] = mapped_column(Float)
    tracking_error: Mapped[Optional[float]] = mapped_column(Float)
    volatility: Mapped[Optional[float]] = mapped_column(Float)
    max_drawdown: Mapped[Optional[float]] = mapped_column(Float)
    average_drawdown: Mapped[Optional[float]] = mapped_column(Float)
    drawdown_duration_days: Mapped[Optional[float]] = mapped_column(Float)
    downside_deviation: Mapped[Optional[float]] = mapped_column(Float)
    sharpe: Mapped[Optional[float]] = mapped_column(Float)
    sortino: Mapped[Optional[float]] = mapped_column(Float)
    calmar: Mapped[Optional[float]] = mapped_column(Float)
    win_rate: Mapped[Optional[float]] = mapped_column(Float)
    profit_factor: Mapped[Optional[float]] = mapped_column(Float)
    average_win: Mapped[Optional[float]] = mapped_column(Float)
    average_loss: Mapped[Optional[float]] = mapped_column(Float)
    payoff_ratio: Mapped[Optional[float]] = mapped_column(Float)
    trade_count: Mapped[Optional[int]] = mapped_column(Integer)
    turnover: Mapped[Optional[float]] = mapped_column(Float)
    holding_period: Mapped[Optional[float]] = mapped_column(Float)
    gross_exposure: Mapped[Optional[float]] = mapped_column(Float)
    net_exposure: Mapped[Optional[float]] = mapped_column(Float)
    leverage: Mapped[Optional[float]] = mapped_column(Float)
    cash: Mapped[Optional[float]] = mapped_column(Float)
    commission: Mapped[Optional[float]] = mapped_column(Float)
    slippage: Mapped[Optional[float]] = mapped_column(Float)
    total_transaction_costs: Mapped[Optional[float]] = mapped_column(Float)
    final_equity: Mapped[Optional[float]] = mapped_column(Float)
    tail_ratio: Mapped[Optional[float]] = mapped_column(Float)
    skewness: Mapped[Optional[float]] = mapped_column(Float)
    kurtosis: Mapped[Optional[float]] = mapped_column(Float)
    var_95: Mapped[Optional[float]] = mapped_column(Float)
    cvar_95: Mapped[Optional[float]] = mapped_column(Float)
    omega_ratio: Mapped[Optional[float]] = mapped_column(Float)
    extras: Mapped[dict] = mapped_column(JSON, default=dict)

    backtest: Mapped[Backtest] = relationship(back_populates="metrics")


class BacktestEquity(Base):
    __tablename__ = "backtest_equity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    strategy_value: Mapped[float] = mapped_column(Float, nullable=False)
    benchmark_value: Mapped[Optional[float]] = mapped_column(Float)
    drawdown: Mapped[Optional[float]] = mapped_column(Float)

    backtest: Mapped[Backtest] = relationship(back_populates="equity")


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trade_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[Optional[float]] = mapped_column(Float)
    exit_price: Mapped[Optional[float]] = mapped_column(Float)
    pnl: Mapped[Optional[float]] = mapped_column(Float)
    return_pct: Mapped[Optional[float]] = mapped_column(Float)
    holding_period: Mapped[Optional[float]] = mapped_column(Float)
    commission: Mapped[Optional[float]] = mapped_column(Float)
    slippage: Mapped[Optional[float]] = mapped_column(Float)
    signal: Mapped[Optional[str]] = mapped_column(String(128))
    raw: Mapped[dict] = mapped_column(JSON, default=dict)

    backtest: Mapped[Backtest] = relationship(back_populates="trades")


class BacktestMonthlyReturn(Base):
    __tablename__ = "backtest_monthly_returns"
    __table_args__ = (UniqueConstraint("backtest_id", "year", "month", name="uq_backtest_monthly"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    return_pct: Mapped[float] = mapped_column(Float, nullable=False)

    backtest: Mapped[Backtest] = relationship(back_populates="monthly_returns")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    object_type: Mapped[str] = mapped_column(String(128), nullable=False)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    before: Mapped[Optional[dict]] = mapped_column(JSON)
    after: Mapped[Optional[dict]] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataSnapshot(Base):
    __tablename__ = "data_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    snapshot_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    symbols: Mapped[dict] = mapped_column(JSON, default=list)
    resolution: Mapped[str] = mapped_column(String(32), default="daily")
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    date_range_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    date_range_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    corporate_actions_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_report: Mapped[dict] = mapped_column(JSON, default=dict)
    provider_capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    superseded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("data_snapshots.id", ondelete="SET NULL"), nullable=True
    )


class ExperimentTrial(Base):
    __tablename__ = "experiment_trials"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    backtest_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("backtests.id", ondelete="SET NULL"), nullable=True, index=True
    )
    data_snapshot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("data_snapshots.id", ondelete="SET NULL"), nullable=True, index=True
    )
    strategy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    universe_key: Mapped[str] = mapped_column(String(128), default="SPY")
    strategy_family: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, index=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    parameter_hash: Mapped[str] = mapped_column(String(64), index=True)
    observed_sharpe: Mapped[Optional[float]] = mapped_column(Float)
    is_oos: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BacktestRollingWindow(Base):
    __tablename__ = "backtest_rolling_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    window_key: Mapped[str] = mapped_column(String(64), nullable=False)
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sharpe: Mapped[Optional[float]] = mapped_column(Float)
    var_95: Mapped[Optional[float]] = mapped_column(Float)
    var_99: Mapped[Optional[float]] = mapped_column(Float)
    probabilistic_sharpe: Mapped[Optional[float]] = mapped_column(Float)
    extras: Mapped[dict] = mapped_column(JSON, default=dict)

    backtest: Mapped[Backtest] = relationship(back_populates="rolling_windows")


class BacktestTimeSeries(Base):
    __tablename__ = "backtest_time_series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    backtest: Mapped[Backtest] = relationship(back_populates="time_series")


class UniverseKind(str, enum.Enum):
    STATIC = "STATIC"


class Universe(Base):
    __tablename__ = "universes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    kind: Mapped[UniverseKind] = mapped_column(
        _enum(UniverseKind, "universe_kind"), default=UniverseKind.STATIC, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    members: Mapped[List["UniverseMember"]] = relationship(
        back_populates="universe", cascade="all, delete-orphan"
    )


class UniverseMember(Base):
    __tablename__ = "universe_members"
    __table_args__ = (
        UniqueConstraint("universe_id", "symbol", "effective_from", name="uq_universe_member_span"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    universe_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("universes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    universe: Mapped[Universe] = relationship(back_populates="members")
