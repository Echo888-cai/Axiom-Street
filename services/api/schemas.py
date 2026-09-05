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
    universe_id: Optional[UUID] = None
    force: bool = False


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
    universe_id: Optional[UUID] = None
    universe_snapshot: Optional[list[Dict[str, Any]]] = None
    result_fingerprint: Optional[str] = None
    cache_hit: bool = False


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
    deflated_sharpe: Optional[float] = None
    probabilistic_sharpe: Optional[float] = None
    dsr_n_trials: Optional[int] = None
    dsr_sr_star: Optional[float] = None
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


class UniverseMemberCreate(BaseModel):
    symbol: str
    effective_from: date
    effective_to: Optional[date] = None
    infer_effective_to_from_data: bool = False


class UniverseMemberUpdate(BaseModel):
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    infer_effective_to_from_data: bool = False


class UniverseMemberOut(ORMModel):
    id: UUID
    universe_id: UUID
    symbol: str
    effective_from: date
    effective_to: Optional[date] = None


class UniverseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    kind: str = "STATIC"
    rules: Optional[dict] = None
    members: list[UniverseMemberCreate] = Field(default_factory=list)


class UniverseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    rules: Optional[dict] = None


class UniverseOut(ORMModel):
    id: UUID
    name: str
    description: Optional[str]
    kind: str
    rules: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    member_count: int = 0
    members: list[UniverseMemberOut] = Field(default_factory=list)


class UniversePage(BaseModel):
    items: list[UniverseOut]
    total: int
    limit: int
    offset: int


class PBOScanCreate(BaseModel):
    strategy_version_id: UUID
    backtest_id: Optional[UUID] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    parameter_key: str = "lookback"
    values: list[int] = Field(default_factory=lambda: [100, 150, 200, 250])


class SensitivityCreate(BaseModel):
    strategy_version_id: UUID
    backtest_id: Optional[UUID] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    parameter_key: str = "lookback"
    values: list[int] = Field(default_factory=lambda: [100, 150, 200, 250, 300])


class CostScanCreate(BaseModel):
    strategy_version_id: UUID
    backtest_id: Optional[UUID] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    costs_bps: list[float] = Field(default_factory=lambda: [0.0, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0])
    realistic_one_way_bps: float = Field(default=5.0, ge=0, le=200)


class BootstrapCreate(BaseModel):
    strategy_version_id: UUID
    backtest_id: Optional[UUID] = None
    n_boot: int = Field(default=2000, ge=200, le=5000)
    confidence_level: float = Field(default=0.95, ge=0.8, lt=1.0)
    method: str = "stationary"
    mean_block_length: Optional[float] = Field(default=None, gt=0)
    seed: Optional[int] = None


class RegimeCreate(BaseModel):
    strategy_version_id: UUID
    backtest_id: Optional[UUID] = None


class SpaCreate(BaseModel):
    strategy_version_id: UUID
    backtest_id: Optional[UUID] = None
    n_boot: int = Field(default=1000, ge=200, le=5000)
    alpha: float = Field(default=0.05, ge=0.01, le=0.2)
    seed: Optional[int] = None


class WalkForwardCreate(BaseModel):
    strategy_version_id: UUID
    backtest_id: Optional[UUID] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    train_years: int = Field(default=3, ge=1, le=20)
    test_years: int = Field(default=1, ge=1, le=10)
    mode: str = "rolling"
    embargo_days: int = Field(default=1, ge=1, le=30)


class ValidationCreate(BaseModel):
    """Unified validation creation — params validated against spec registry."""

    kind: str
    strategy_version_id: UUID
    backtest_id: Optional[UUID] = None
    params: Dict[str, Any] = Field(default_factory=dict)


class ValidationRunOut(ORMModel):
    id: UUID
    strategy_id: Optional[UUID] = None
    strategy_version_id: Optional[UUID] = None
    backtest_id: Optional[UUID] = None
    kind: str
    status: str = "COMPLETED"
    progress_step: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)
    passed: bool
    error: Dict[str, Any] | None = None
    created_at: datetime
    finished_at: Optional[datetime] = None


class ValidationSpecOut(BaseModel):
    kind: str
    display_name: str
    description: str
    auto_on_backtest: bool
    params_schema: Dict[str, Any]


class ValidationPage(BaseModel):
    items: list[ValidationRunOut]
    total: int
    limit: int
    offset: int
    gates: Dict[str, Any] = Field(default_factory=dict)


class SyntaxCheckIn(BaseModel):
    code: str


class SyntaxCheckOut(BaseModel):
    ok: bool
    message: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None


class LspPositionIn(BaseModel):
    code: str
    line: int
    column: int


class LspCompletion(BaseModel):
    label: str
    insert: str
    kind: str
    detail: Optional[str] = None


class LspCompleteOut(BaseModel):
    items: list[LspCompletion]
    syntax: SyntaxCheckOut
    error: Optional[str] = None


class LspHoverOut(BaseModel):
    contents: Optional[str] = None
    error: Optional[str] = None


class ResearchNoteCreate(BaseModel):
    strategy_id: UUID
    strategy_version_id: Optional[UUID] = None
    backtest_id: Optional[UUID] = None
    title: Optional[str] = None
    hypothesis: Optional[str] = None
    method: Optional[str] = None
    conclusion: Optional[str] = None
    failure_modes: Optional[str] = None


class ResearchNoteUpdate(BaseModel):
    strategy_version_id: Optional[UUID] = None
    backtest_id: Optional[UUID] = None
    title: Optional[str] = None
    hypothesis: Optional[str] = None
    method: Optional[str] = None
    conclusion: Optional[str] = None
    failure_modes: Optional[str] = None


class ResearchNoteOut(ORMModel):
    id: UUID
    strategy_id: UUID
    strategy_version_id: Optional[UUID] = None
    backtest_id: Optional[UUID] = None
    title: str
    hypothesis: str
    method: str
    conclusion: str
    failure_modes: str
    created_at: datetime
    updated_at: datetime


class ResearchNotePage(BaseModel):
    items: list[ResearchNoteOut]
    total: int
    limit: int
    offset: int
