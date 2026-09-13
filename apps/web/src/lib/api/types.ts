// Contract-first API types (W3-6, scope: frontend hybrid alias + checks).
//
// Every shape the OpenAPI spec models is aliased straight from
// api-types.gen.ts — that file is the single source of truth and the CI
// drift guard (`codegen:types && git diff --exit-code`) owns it. Fields the
// backend leaves unmodeled (bare dicts / anonymous responses) keep narrow
// local read models, keyed to the keys the backend actually writes; the
// type-level checks at the bottom of this file pin each read model as a
// structural subtype of its contract counterpart so unmodeled drift stays
// visible. Governance: docs/PLAN.md section 6.2 (API contracts).

import type { components, operations } from "../api-types.gen";

type S = components["schemas"];

// ---------- whole-shape aliases: the contract owns the field set ----------

export type Strategy = S["StrategyOut"];
export type StrategyVersion = S["StrategyVersionOut"];
export type BacktestMetrics = S["BacktestMetricsOut"];
export type EquityPoint = S["EquityPoint"];
export type Trade = S["TradeOut"];
export type TimeSeriesPoint = S["TimeSeriesPointOut"];
export type LspCompletion = S["LspCompletion"];
export type MonthlyReturn = S["MonthlyReturnOut"];
export type MaeMfePoint = S["MaeMfePoint"];
export type ResearchNote = S["ResearchNoteOut"];
export type UniverseMember = S["UniverseMemberOut"];
export type ValidationSpec = S["ValidationSpecOut"];

// Copilot context (P5-1): the spec models every nested fact shape, so the
// whole payload aliases the contract directly.
export type CopilotContext = S["CopilotContextOut"];
export type CopilotSnapshotFacts = S["CopilotSnapshotFacts"];
export type CopilotGateFacts = S["CopilotGateFacts"];

// Copilot synthesize ledger (P5-2): the spec models rows and the accepted
// response fully, so both alias the generated contract.
export type CopilotInsight = S["CopilotInsightOut"];
export type CopilotSynthesizeAccepted = S["CopilotSynthesizeAccepted"];

// Copilot suggestion cards (P5-3): deterministic cards, the recommendation
// row and the enqueue ack are all fully modeled by the spec, so all alias it.
export type CopilotSuggestionCard = S["CopilotSuggestionCard"];
export type CopilotSuggestions = S["CopilotSuggestionsOut"];
export type CopilotSuggestion = S["CopilotSuggestionOut"];
export type CopilotSuggestAccepted = S["CopilotSuggestAccepted"];

// Guided research conversation (P5-4): the provider only receives aggregate
// Copilot facts; the ledger row and enqueue acknowledgement are contract-owned.
export type CopilotChatMessage = S["CopilotChatOut"];
export type CopilotChatAccepted = S["CopilotChatAccepted"];

// Portfolio attribution (E8-1): portfolio configuration and the additive
// Brinson result are both contract-owned API shapes.
export type Portfolio = S["PortfolioOut"];
export type PortfolioAllocation = S["PortfolioAllocationOut"];
export type PortfolioAttribution = S["PortfolioAttributionOut"];

// Paper execution and risk summary contracts (E6-1 / Phase 9 UI).
export type PaperOrder = S["PaperOrderOut"];
export type PaperOrderAccepted = S["PaperOrderAccepted"];
export type PaperPositions = S["PaperPositionsOut"];
export type PaperReconciliation = S["PaperReconciliationOut"];
export type RiskSummary = S["RiskSummaryOut"];

export type HealthCheck = {
  ok: boolean;
  note?: string | null;
  reported_at?: string | null;
  age_seconds?: number | null;
  heartbeat_ttl_seconds?: number | null;
  image?: string | null;
  docker_available?: boolean;
  network?: string;
  rootfs_read_only?: boolean;
  non_root?: boolean;
  seccomp?: string;
  capabilities_dropped?: string;
  no_new_privileges?: boolean;
  tmpfs?: string | null;
};

export type HealthStatus = {
  status: "ok" | "degraded" | "down" | string;
  service: string;
  version: string;
  checks: {
    postgres?: HealthCheck;
    redis?: HealthCheck;
    docker?: HealthCheck;
    worker?: HealthCheck;
    security?: HealthCheck;
    [key: string]: HealthCheck | undefined;
  };
};

// spec kinds are plain strings; the UI narrows to the eight known kinds.
export type ValidationKind =
  | "walk_forward"
  | "dsr"
  | "pbo"
  | "sensitivity"
  | "cost"
  | "bootstrap"
  | "regime"
  | "spa";

// ---------- narrowed read models: contract base + local shape for fields
// the backend returns as bare dicts but the UI actually reads ----------

// Backend writes {code, message} and adds line on engine errors
// (services/worker/tasks/backtests.py).
export type BacktestError = { code?: string; message?: string; line?: number };

export type BacktestUniverseMember = {
  symbol: string;
  effective_from: string;
  effective_to: string | null;
};

export type Backtest = Omit<S["BacktestOut"], "error" | "universe_snapshot"> & {
  error: BacktestError | null;
  universe_snapshot?: BacktestUniverseMember[] | null;
};

// Backend writes {code, message} for failed runs, same shape as BacktestError
// (services/worker/tasks/backtests.py / scans.py).
export type ValidationRun = Omit<S["ValidationRunOut"], "error"> & {
  error?: BacktestError | null;
};

// Rules mirror quant/data/universe_rules.py UniverseRuleSet keys.
export type Universe = Omit<S["UniverseOut"], "rules"> & {
  rules?: {
    min_price?: number;
    min_adv_usd?: number;
    lookback_days?: number;
    min_market_cap_usd?: number;
    sectors?: string[];
    industries?: string[];
  } | null;
};

// by_snapshot rows are returned unmodeled; narrow for trial-stats display.
export type TrialStats = Omit<S["TrialStatsOut"], "by_snapshot"> & {
  by_snapshot?: Array<{
    data_snapshot_id: string | null;
    snapshot_key: string | null;
    count: number;
    sharpe_mean: number | null;
    sharpe_var: number | null;
    sharpe_max: number | null;
    duplicate_parameter_hashes: number;
  }>;
};

// ---------- local-only read models: the API has no named schema for these
// responses yet (bare dict in OpenAPI). Shape stays hand-maintained until
// the backend models them; endpoint pins at the bottom keep the mapping
// honest. ----------

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

// The spec's ValidationPage carries a bare `gates` object; narrow read model
// below, guarded against ValidationPage by the compound check at the bottom.
export type ValidationGates = {
  validated_requires?: string[];
  available?: string[];
  missing?: string[];
  note?: string;
};

// Metrics the backend attaches per compare series. Derived from the
// BacktestMetricsOut schema by key, so renames/type changes in the contract
// surface here at compile time; the endpoint only ever writes these keys.
export type CompareSeriesMetrics = {
  [K in
    | "final_equity"
    | "total_return"
    | "cagr"
    | "sharpe"
    | "max_drawdown"
    | "volatility"
    | "trade_count"]: NonNullable<S["BacktestMetricsOut"][K]>;
};

export type CompareSeries = {
  id: string;
  label: string;
  data: Array<{ time: string; value: number }>;
  metrics?: CompareSeriesMetrics | null;
};

export type CompareEquityResponse = {
  series: CompareSeries[];
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

// ---------- structural checks: each read model must stay a subtype of its
// contract counterpart (exported so lint/compilers treat them as used) ----------

type Check<T extends true> = T;
type Extends<A, B> = [A] extends [B] ? true : false;

export type _C_Backtest = Check<Extends<Backtest, S["BacktestOut"]>>;
export type _C_ValidationRun = Check<
  Extends<ValidationRun, S["ValidationRunOut"]>
>;
export type _C_Universe = Check<Extends<Universe, S["UniverseOut"]>>;
export type _C_TrialStats = Check<Extends<TrialStats, S["TrialStatsOut"]>>;
export type _C_Strategy = Check<Extends<Strategy, S["StrategyOut"]>>;
export type _C_StrategyVersion = Check<
  Extends<StrategyVersion, S["StrategyVersionOut"]>
>;
export type _C_BacktestMetrics = Check<
  Extends<BacktestMetrics, S["BacktestMetricsOut"]>
>;
export type _C_EquityPoint = Check<Extends<EquityPoint, S["EquityPoint"]>>;
export type _C_Trade = Check<Extends<Trade, S["TradeOut"]>>;
export type _C_TimeSeriesPoint = Check<
  Extends<TimeSeriesPoint, S["TimeSeriesPointOut"]>
>;
export type _C_LspCompletion = Check<Extends<LspCompletion, S["LspCompletion"]>>;
export type _C_MonthlyReturn = Check<
  Extends<MonthlyReturn, S["MonthlyReturnOut"]>
>;
export type _C_MaeMfePoint = Check<Extends<MaeMfePoint, S["MaeMfePoint"]>>;
export type _C_ResearchNote = Check<
  Extends<ResearchNote, S["ResearchNoteOut"]>
>;
export type _C_UniverseMember = Check<
  Extends<UniverseMember, S["UniverseMemberOut"]>
>;
export type _C_ValidationSpec = Check<
  Extends<ValidationSpec, S["ValidationSpecOut"]>
>;

// Page<T> mirrors the spec's page envelopes; pins keep the generic honest.
export type _C_PageBacktest = Check<
  Extends<Page<Backtest>, S["BacktestPage"]>
>;
export type _C_PageStrategy = Check<
  Extends<Page<Strategy>, S["StrategyPage"]>
>;
export type _C_PageEquity = Check<Extends<Page<EquityPoint>, S["EquityPage"]>>;
export type _C_PageTrade = Check<Extends<Page<Trade>, S["TradePage"]>>;
export type _C_PageUniverse = Check<Extends<Page<Universe>, S["UniversePage"]>>;
export type _C_PageValidation = Check<
  Extends<Page<ValidationRun>, S["ValidationPage"]>
>;
export type _C_PageValidationGates = Check<
  Extends<Page<ValidationRun> & { gates?: ValidationGates }, S["ValidationPage"]>
>;
export type _C_PageResearch = Check<
  Extends<Page<ResearchNote>, S["ResearchNotePage"]>
>;

// Endpoint pins for unmodeled responses: the response bodies are bare dicts
// in the spec, so the subtype checks above cannot protect them; these pins
// fail loudly if the route/method/response is remodeled, and then the local
// read model above must follow.
type OpBody<K extends keyof operations> =
  operations[K]["responses"] extends {
    200: { content: { "application/json": infer J } };
  }
    ? J
    : never;

export type _C_DataStatus = Check<
  Extends<DataStatus, OpBody<"get_data_status_api_v1_data_status_get">>
>;
export type _C_IngestJob = Check<
  Extends<
    IngestJob,
    OpBody<"get_ingest_job_api_v1_data_ingest__job_id__get">
  >
>;
export type _C_DataSnapshot = Check<
  Extends<DataSnapshot, OpBody<"list_snapshots_api_v1_data_snapshots_get">>
>;
export type _C_CompareEquity = Check<
  Extends<
    CompareEquityResponse,
    OpBody<"compare_equity_api_v1_backtests_compare_equity_get">
  >
>;
