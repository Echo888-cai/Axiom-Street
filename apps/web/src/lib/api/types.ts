export type Strategy = {
  id: string;
  name: string;
  description: string | null;
  status: string;
  asset_class: string;
  benchmark: string;
  created_at: string;
  updated_at: string;
  latest_version?: StrategyVersion | null;
};

export type StrategyVersion = {
  id: string;
  strategy_id: string;
  version: number;
  code: string;
  config: Record<string, unknown>;
  commit_message: string | null;
  created_by: string;
  created_at: string;
};

export type Backtest = {
  id: string;
  strategy_version_id: string;
  start_date: string;
  end_date: string;
  benchmark: string;
  initial_capital: number;
  status: string;
  engine_version: string | null;
  data_version: string | null;
  parameters: Record<string, unknown>;
  progress_step: string | null;
  error: { message?: string; line?: number; code?: string } | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  strategy_id?: string | null;
  strategy_name?: string | null;
  version_number?: number | null;
  total_return?: number | null;
  sharpe?: number | null;
  max_drawdown?: number | null;
  trade_count?: number | null;
  final_equity?: number | null;
  data_snapshot_id?: string | null;
  universe_id?: string | null;
  universe_snapshot?: Array<{
    symbol: string;
    effective_from: string;
    effective_to: string | null;
  }> | null;
  result_fingerprint?: string | null;
  cache_hit?: boolean;
};

export type BacktestMetrics = {
  backtest_id: string;
  total_return: number | null;
  cagr: number | null;
  sharpe: number | null;
  max_drawdown: number | null;
  volatility: number | null;
  win_rate: number | null;
  trade_count: number | null;
  final_equity: number | null;
  benchmark_return: number | null;
  excess_return: number | null;
  alpha_capm: number | null;
  beta: number | null;
  information_ratio: number | null;
  tracking_error: number | null;
  sortino: number | null;
  calmar: number | null;
  commission: number | null;
  deflated_sharpe: number | null;
  probabilistic_sharpe: number | null;
  dsr_n_trials: number | null;
  dsr_sr_star: number | null;
  tail_ratio?: number | null;
  skewness?: number | null;
  kurtosis?: number | null;
  var_95?: number | null;
  cvar_95?: number | null;
  omega_ratio?: number | null;
  turnover?: number | null;
  gross_exposure?: number | null;
  net_exposure?: number | null;
  extras?: Record<string, unknown>;
  [key: string]: unknown;
};

export type EquityPoint = {
  ts: string;
  strategy_value: number;
  benchmark_value: number | null;
  drawdown: number | null;
};

export type Trade = {
  id: number;
  trade_date: string;
  ticker: string;
  direction: string;
  quantity: number;
  entry_price: number | null;
  exit_price: number | null;
  pnl: number | null;
  return_pct: number | null;
  holding_period: number | null;
  commission: number | null;
  slippage: number | null;
  signal: string | null;
};

export type TimeSeriesPoint = {
  name: string;
  ts: string;
  value: number;
};

export type LspCompletion = {
  label: string;
  insert: string;
  kind: string;
  detail: string | null;
};

export type MonthlyReturn = {
  year: number;
  month: number;
  return_pct: number;
};

export type ResearchNote = {
  id: string;
  strategy_id: string;
  strategy_version_id: string | null;
  backtest_id: string | null;
  title: string;
  hypothesis: string;
  method: string;
  conclusion: string;
  failure_modes: string;
  created_at: string;
  updated_at: string;
};

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type TrialStats = {
  strategy_id: string;
  family_id: string | null;
  total_trials: number;
  by_snapshot: Array<{
    data_snapshot_id: string | null;
    snapshot_key: string | null;
    count: number;
    sharpe_mean: number | null;
    sharpe_var: number | null;
    sharpe_max: number | null;
    duplicate_parameter_hashes: number;
  }>;
};

export type ValidationKind =
  | "walk_forward"
  | "dsr"
  | "pbo"
  | "sensitivity"
  | "cost"
  | "bootstrap"
  | "regime"
  | "spa";

export type ValidationSpec = {
  kind: ValidationKind;
  display_name: string;
  description: string;
  auto_on_backtest: boolean;
  params_schema: Record<string, unknown>;
};

export type ValidationRun = {
  id: string;
  strategy_id: string | null;
  strategy_version_id: string | null;
  backtest_id: string | null;
  kind: string;
  status: string;
  progress_step: string | null;
  params: Record<string, unknown>;
  result: Record<string, unknown>;
  passed: boolean;
  error: { code?: string; message?: string } | null;
  created_at: string;
  finished_at: string | null;
};

export type ValidationSpecOut = {
  kind: ValidationKind;
  display_name: string;
  description: string;
  auto_on_backtest: boolean;
  params_schema: Record<string, unknown>;
};

export type UniverseMember = {
  id: string;
  universe_id: string;
  symbol: string;
  effective_from: string;
  effective_to: string | null;
};

export type Universe = {
  id: string;
  name: string;
  description: string | null;
  kind: string;
  rules?: {
    min_price?: number;
    min_adv_usd?: number;
    lookback_days?: number;
    min_market_cap_usd?: number;
    sectors?: string[];
    industries?: string[];
  } | null;
  created_at: string;
  updated_at: string;
  member_count: number;
  members: UniverseMember[];
};

export type IngestJob = {
  id: string;
  status: string;
  progress_step: string | null;
  symbols: string[];
  start: string;
  end: string | null;
  provider: string;
  mode: string;
  reconcile_with: string | null;
  convert_lean: boolean;
  current_symbol: string | null;
  completed_symbols: number;
  total_symbols: number;
  result: {
    ok?: boolean;
    symbols?: string[];
    snapshot_key?: string;
    quality_report?: DataStatus["quality_report"];
  } | null;
  error: { code?: string; message?: string } | null;
  data_snapshot_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
};

export type DataSnapshot = {
  id: string;
  snapshot_key: string;
  symbols: string[] | string;
  provider: string;
  row_count: number;
  content_sha256: string;
  corporate_actions_verified: boolean;
  superseded_by: string | null;
  created_at: string | null;
};

export type DataStatus = {
  ready: boolean;
  lean_ready: boolean;
  parquet_path: string | null;
  lean_path: string | null;
  manifest: Record<string, unknown>;
  providers: Record<string, unknown>;
  docker_required_for_backtest: boolean;
  snapshot_key?: string | null;
  corporate_actions_verified?: boolean | null;
  symbols?: string[];
  quality_report?: {
    has_blocking_issues?: boolean;
    issues?: Array<{
      rule: string;
      severity: string;
      message: string;
      count?: number;
    }>;
  };
  lean_engine?: {
    engine: string;
    image: string;
    docker_available: boolean;
    source?: string;
    reported_at?: string | null;
    note?: string | null;
  };
  market_reconcile?: {
    enabled: boolean;
    interval_seconds: number;
    provider: string;
    reconcile_with: string | null;
  };
  latest_ingest_job?: IngestJob | null;
  ingest_limits?: {
    max_symbols: number;
    rps: number;
    concurrency: number;
  };
  reconcile_with?: string | null;
  reconcile_reports?: Array<{
    symbol?: string;
    primary_source?: string;
    secondary_source?: string;
    compared_bars?: number;
    suspect_bars?: number;
    has_blocking_issues?: boolean;
    issues?: Array<{
      rule: string;
      severity: string;
      message: string;
      examples?: string[];
    }>;
  }>;
  inferred_delistings?: Array<{
    symbol: string;
    last_bar: string;
    effective_to: string;
  }>;
};
