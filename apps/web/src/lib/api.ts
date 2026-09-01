const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    let message = text || `请求失败：${res.status}`;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      if (typeof parsed.detail === "string") {
        message = parsed.detail;
      } else if (Array.isArray(parsed.detail) && parsed.detail[0] && typeof parsed.detail[0] === "object") {
        const first = parsed.detail[0] as { msg?: string };
        if (first.msg) message = first.msg;
      } else if (parsed.detail && typeof parsed.detail === "object") {
        const detail = parsed.detail as { message?: string; msg?: string };
        message = detail.message || detail.msg || JSON.stringify(parsed.detail);
      }
    } catch {
      /* keep raw text */
    }
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

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
  error: { message?: string } | null;
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

export type MonthlyReturn = {
  year: number;
  month: number;
  return_pct: number;
};

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

function unwrapList<T>(data: T[] | Page<T>): T[] {
  return Array.isArray(data) ? data : data.items;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),
  listStrategies: () =>
    request<Page<Strategy> | Strategy[]>("/api/v1/strategies").then(unwrapList),
  getStrategy: (id: string) => request<Strategy>(`/api/v1/strategies/${id}`),
  updateStrategy: (
    id: string,
    body: { name?: string; description?: string },
  ) =>
    request<Strategy>(`/api/v1/strategies/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  createStrategy: (body: {
    name: string;
    description?: string;
    code?: string;
    config?: Record<string, unknown>;
  }) =>
    request<Strategy>("/api/v1/strategies", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createVersion: (
    strategyId: string,
    body: { code: string; config?: Record<string, unknown>; commit_message?: string },
  ) =>
    request<StrategyVersion>(`/api/v1/strategies/${strategyId}/versions`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listVersions: (strategyId: string) =>
    request<StrategyVersion[]>(`/api/v1/strategies/${strategyId}/versions`),
  deleteStrategy: (id: string) =>
    request<void>(`/api/v1/strategies/${id}`, { method: "DELETE" }),
  getTrialStats: (id: string) =>
    request<TrialStats>(`/api/v1/strategies/${id}/trial-stats`),
  listBacktests: () =>
    request<Page<Backtest> | Backtest[]>("/api/v1/backtests").then(unwrapList),
  getBacktest: (id: string) => request<Backtest>(`/api/v1/backtests/${id}`),
  cancelBacktest: (id: string) =>
    request<Backtest>(`/api/v1/backtests/${id}/cancel`, { method: "POST" }),
  createBacktest: (body: {
    strategy_version_id: string;
    start_date: string;
    end_date: string;
    benchmark?: string;
    initial_capital?: number;
  }) =>
    request<Backtest>("/api/v1/backtests", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getMetrics: (id: string) => request<BacktestMetrics>(`/api/v1/backtests/${id}/metrics`),
  getEquity: (id: string) =>
    request<Page<EquityPoint> | EquityPoint[]>(`/api/v1/backtests/${id}/equity`).then(unwrapList),
  getTrades: (id: string) =>
    request<Page<Trade> | Trade[]>(`/api/v1/backtests/${id}/trades`).then(unwrapList),
  getMonthlyReturns: (id: string) =>
    request<MonthlyReturn[]>(`/api/v1/backtests/${id}/monthly-returns`),
  eventsUrl: (id: string) => `${API_URL}/api/v1/backtests/${id}/events`,
  dataStatus: () => request<DataStatus>("/api/v1/data/status"),
  ingestSpy: (body?: { start?: string; provider?: string }) =>
    request<{ ok: boolean; status: DataStatus }>("/api/v1/data/ingest/spy", {
      method: "POST",
      body: JSON.stringify(body || { provider: "auto", start: "2010-01-01" }),
    }),
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
  quality_report?: {
    has_blocking_issues?: boolean;
    issues?: Array<{ rule: string; severity: string; message: string; count?: number }>;
  };
  lean_engine?: {
    engine: string;
    image: string;
    docker_available: boolean;
  };
};

export { unwrapList };
