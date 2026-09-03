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
  data_snapshot_id?: string | null;
  universe_id?: string | null;
  universe_snapshot?: Array<{
    symbol: string;
    effective_from: string;
    effective_to: string | null;
  }> | null;
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
  listValidation: (params?: { strategy_id?: string; kind?: string }) => {
    const search = new URLSearchParams();
    if (params?.strategy_id) search.set("strategy_id", params.strategy_id);
    if (params?.kind) search.set("kind", params.kind);
    const q = search.toString();
    return request<{
      items: ValidationRun[];
      total: number;
      limit: number;
      offset: number;
      gates: {
        validated_requires?: string[];
        available?: string[];
        missing?: string[];
        note?: string;
      };
    }>(`/api/v1/validation${q ? `?${q}` : ""}`);
  },
  getValidationRun: (id: string) => request<ValidationRun>(`/api/v1/validation/${id}`),
  createWalkForward: (body: {
    strategy_version_id: string;
    backtest_id?: string;
    start_date?: string;
    end_date?: string;
    train_years?: number;
    test_years?: number;
    mode?: "rolling" | "anchored";
    embargo_days?: number;
  }) =>
    request<ValidationRun>("/api/v1/validation/walk-forward", {
      method: "POST",
      body: JSON.stringify(body),
    }),
    createPboScan: (body: {
    strategy_version_id: string;
    backtest_id?: string;
    start_date?: string;
    end_date?: string;
    parameter_key?: string;
    values: number[];
  }) =>
    request<ValidationRun>("/api/v1/validation/pbo", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createSensitivityScan: (body: {
    strategy_version_id: string;
    backtest_id?: string;
    start_date?: string;
    end_date?: string;
    parameter_key?: string;
    values: number[];
  }) =>
    request<ValidationRun>("/api/v1/validation/sensitivity", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createCostScan: (body: {
    strategy_version_id: string;
    backtest_id?: string;
    start_date?: string;
    end_date?: string;
    costs_bps: number[];
    realistic_one_way_bps?: number;
  }) =>
    request<ValidationRun>("/api/v1/validation/cost", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listBacktests: (params?: { strategy_id?: string; status?: string }) => {
    const search = new URLSearchParams();
    if (params?.strategy_id) search.set("strategy_id", params.strategy_id);
    if (params?.status) search.set("status", params.status);
    const q = search.toString();
    return request<Page<Backtest> | Backtest[]>(`/api/v1/backtests${q ? `?${q}` : ""}`).then(
      unwrapList,
    );
  },
  getBacktest: (id: string) => request<Backtest>(`/api/v1/backtests/${id}`),
  cancelBacktest: (id: string) =>
    request<Backtest>(`/api/v1/backtests/${id}/cancel`, { method: "POST" }),
  createBacktest: (body: {
    strategy_version_id: string;
    start_date: string;
    end_date: string;
    benchmark?: string;
    initial_capital?: number;
    data_snapshot_id?: string;
    universe?: string[];
    universe_id?: string;
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
  reconcileMarket: (force = false) =>
    request<{ ok: boolean; skipped: boolean; job: IngestJob; symbols: string[] }>(
      `/api/v1/data/reconcile?force=${force ? "true" : "false"}`,
      { method: "POST" },
    ),
  ingest: (body?: {
    symbols?: string[];
    start?: string;
    provider?: string;
    mode?: "full" | "incremental";
    reconcile_with?: string;
  }) =>
    request<IngestJob>("/api/v1/data/ingest", {
      method: "POST",
      body: JSON.stringify({
        symbols: body?.symbols?.length ? body.symbols : ["SPY"],
        provider: body?.provider || "auto",
        start: body?.start || "2010-01-01",
        mode: body?.mode || "full",
        reconcile_with: body?.reconcile_with,
      }),
    }),
  getIngestJob: (id: string) => request<IngestJob>(`/api/v1/data/ingest/${id}`),
  ingestEventsUrl: (id: string) => `${API_URL}/api/v1/data/ingest/${id}/events`,
  ingestSpy: (body?: { start?: string; provider?: string }) =>
    request<IngestJob>("/api/v1/data/ingest/spy", {
      method: "POST",
      body: JSON.stringify(body || { provider: "auto", start: "2010-01-01" }),
    }),
  listSnapshots: () =>
    request<{ total: number; items: DataSnapshot[] }>("/api/v1/data/snapshots"),
  listUniverses: () =>
    request<Page<Universe>>("/api/v1/universes").then(unwrapList),
  getUniverse: (id: string) => request<Universe>(`/api/v1/universes/${id}`),
  createUniverse: (body: {
    name: string;
    description?: string;
    kind?: string;
    rules?: {
      min_price?: number;
      min_adv_usd?: number;
      lookback_days?: number;
      min_market_cap_usd?: number;
      sectors?: string[];
      industries?: string[];
    };
  }) =>
    request<Universe>("/api/v1/universes", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateUniverse: (id: string, body: { name?: string; description?: string }) =>
    request<Universe>(`/api/v1/universes/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteUniverse: (id: string) =>
    request<void>(`/api/v1/universes/${id}`, { method: "DELETE" }),
  addUniverseMember: (
    universeId: string,
    body: {
      symbol: string;
      effective_from: string;
      effective_to?: string | null;
      infer_effective_to_from_data?: boolean;
    },
  ) =>
    request<UniverseMember>(`/api/v1/universes/${universeId}/members`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteUniverseMember: (universeId: string, memberId: string) =>
    request<void>(`/api/v1/universes/${universeId}/members/${memberId}`, {
      method: "DELETE",
    }),
  syncUniverseDelistings: () =>
    request<{
      applied: Array<{ universe_id: string; symbol: string; effective_to: string }>;
      skipped: Array<{ universe_id: string; symbol: string; reason?: string }>;
      errors: Array<{ universe_id?: string; symbol?: string; message: string }>;
      inferred?: Array<{ symbol: string; last_bar: string; effective_to: string }>;
    }>("/api/v1/universes/sync-delistings", { method: "POST" }),
  rebuildUniverse: (id: string) =>
    request<Universe>(`/api/v1/universes/${id}/rebuild`, { method: "POST" }),
  previewUniverse: (
    universeId: string,
    params: { as_of?: string; start?: string; end?: string },
  ) => {
    const search = new URLSearchParams();
    if (params.as_of) search.set("as_of", params.as_of);
    if (params.start) search.set("start", params.start);
    if (params.end) search.set("end", params.end);
    return request<{
      as_of?: string;
      start?: string;
      end?: string;
      symbols: string[];
      memberships?: Array<{
        symbol: string;
        effective_from: string;
        effective_to: string | null;
      }>;
    }>(`/api/v1/universes/${universeId}/constituents?${search.toString()}`);
  },
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
    issues?: Array<{ rule: string; severity: string; message: string; count?: number }>;
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
    issues?: Array<{ rule: string; severity: string; message: string; examples?: string[] }>;
  }>;
  inferred_delistings?: Array<{
    symbol: string;
    last_bar: string;
    effective_to: string;
  }>;
};

export { unwrapList };
