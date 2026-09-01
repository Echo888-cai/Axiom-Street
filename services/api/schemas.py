from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from services.api.models import BacktestStatus, StrategyStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StrategyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    asset_class: str = "equity"
    benchmark: str = "SPY"
    code: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    commit_message: Optional[str] = "Initial version"


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[StrategyStatus] = None
    asset_class: Optional[str] = None
    benchmark: Optional[str] = None


class StrategyVersionCreate(BaseModel):
    code: str
    config: Dict[str, Any] = Field(default_factory=dict)
    commit_message: Optional[str] = None


class StrategyVersionOut(ORMModel):
    id: UUID
    strategy_id: UUID
    version: int
    code: str
    config: Dict[str, Any]
    commit_message: Optional[str]
    created_by: str
    created_at: datetime


class StrategyOut(ORMModel):
    id: UUID
    name: str
    description: Optional[str]
    status: StrategyStatus
    asset_class: str
    benchmark: str
    family_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    latest_version: Optional[StrategyVersionOut] = None


class BacktestCreate(BaseModel):
    strategy_version_id: UUID
    start_date: date
    end_date: date
    benchmark: str = "SPY"
    initial_capital: float = 100_000.0
    parameters: Dict[str, Any] = Field(default_factory=dict)
    data_snapshot_id: Optional[UUID] = None
    universe: Optional[list[str]] = None


class BacktestOut(ORMModel):
    id: UUID
    strategy_version_id: UUID
    start_date: date
    end_date: date
    benchmark: str
    initial_capital: float
    status: BacktestStatus
    engine_version: Optional[str]
    data_version: Optional[str]
    parameters: Dict[str, Any]
    progress_step: Optional[str]
    error: Dict[str, Any] | None
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime
    strategy_id: Optional[UUID] = None
    strategy_name: Optional[str] = None
    version_number: Optional[int] = None
    total_return: Optional[float] = None
    sharpe: Optional[float] = None
    max_drawdown: Optional[float] = None
    trade_count: Optional[int] = None
    final_equity: Optional[float] = None
    data_snapshot_id: Optional[UUID] = None


class BacktestMetricsOut(ORMModel):
    backtest_id: UUID
    total_return: Optional[float] = None
    cagr: Optional[float] = None
    annualized_return: Optional[float] = None
    benchmark_return: Optional[float] = None
    excess_return: Optional[float] = None
    alpha_capm: Optional[float] = None
    beta: Optional[float] = None
    information_ratio: Optional[float] = None
    tracking_error: Optional[float] = None
    volatility: Optional[float] = None
    max_drawdown: Optional[float] = None
    average_drawdown: Optional[float] = None
    drawdown_duration_days: Optional[float] = None
    downside_deviation: Optional[float] = None
    sharpe: Optional[float] = None
    sortino: Optional[float] = None
    calmar: Optional[float] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    average_win: Optional[float] = None
    average_loss: Optional[float] = None
    payoff_ratio: Optional[float] = None
    trade_count: Optional[int] = None
    turnover: Optional[float] = None
    holding_period: Optional[float] = None
    gross_exposure: Optional[float] = None
    net_exposure: Optional[float] = None
    leverage: Optional[float] = None
    cash: Optional[float] = None
    commission: Optional[float] = None
    slippage: Optional[float] = None
    total_transaction_costs: Optional[float] = None
    final_equity: Optional[float] = None
    tail_ratio: Optional[float] = None
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    var_95: Optional[float] = None
    cvar_95: Optional[float] = None
    omega_ratio: Optional[float] = None
    extras: Dict[str, Any] = Field(default_factory=dict)


class EquityPoint(BaseModel):
    ts: datetime
    strategy_value: float
    benchmark_value: Optional[float] = None
    drawdown: Optional[float] = None


class TradeOut(ORMModel):
    id: int
    trade_date: datetime
    ticker: str
    direction: str
    quantity: float
    entry_price: Optional[float]
    exit_price: Optional[float]
    pnl: Optional[float]
    return_pct: Optional[float]
    holding_period: Optional[float]
    commission: Optional[float]
    slippage: Optional[float]
    signal: Optional[str]


class MonthlyReturnOut(BaseModel):
    year: int
    month: int
    return_pct: float


class StrategyPage(BaseModel):
    items: list[StrategyOut]
    total: int
    limit: int
    offset: int


class BacktestPage(BaseModel):
    items: list[BacktestOut]
    total: int
    limit: int
    offset: int


class EquityPage(BaseModel):
    items: list[EquityPoint]
    total: int
    limit: int
    offset: int


class TradePage(BaseModel):
    items: list[TradeOut]
    total: int
    limit: int
    offset: int


class RollingWindowOut(BaseModel):
    window_key: str
    period_end: Optional[datetime] = None
    sharpe: Optional[float] = None
    var_95: Optional[float] = None
    var_99: Optional[float] = None
    probabilistic_sharpe: Optional[float] = None
    extras: Dict[str, Any] = Field(default_factory=dict)


class TimeSeriesPointOut(BaseModel):
    name: str
    ts: datetime
    value: float


class TrialSnapshotStats(BaseModel):
    data_snapshot_id: Optional[UUID] = None
    snapshot_key: Optional[str] = None
    count: int
    sharpe_mean: Optional[float] = None
    sharpe_var: Optional[float] = None
    sharpe_max: Optional[float] = None
    duplicate_parameter_hashes: int = 0


class TrialStatsOut(BaseModel):
    strategy_id: UUID
    family_id: Optional[UUID] = None
    total_trials: int
    by_snapshot: list[TrialSnapshotStats] = Field(default_factory=list)


class AuditLogOut(ORMModel):
    id: int
    actor: str
    action: str
    object_type: str
    object_id: str
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    timestamp: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    total: int
    limit: int
    offset: int


class BacktestLogsOut(BaseModel):
    stdout: str = ""
    stderr: str = ""


class HealthOut(BaseModel):
    status: str
    service: str
    version: str
    checks: Dict[str, Any] = Field(default_factory=dict)
