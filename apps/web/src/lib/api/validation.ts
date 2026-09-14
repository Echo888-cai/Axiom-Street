import { request } from "./http";
import type {
  Page,
  TrialStats,
  ValidationEvidence,
  ValidationGates,
  ValidationRun,
  ValidationSpec,
} from "./types";

export const validationApi = {
  // P3.3 整组验证计划：适用条件/样本/参数读取/资源估计/冻结区间。
  validationPlan: (strategyVersionId: string, backtestId?: string) => {
    const search = new URLSearchParams({ strategy_version_id: strategyVersionId });
    if (backtestId) search.set("backtest_id", backtestId);
    return request<Record<string, unknown>>(`/api/v1/validation/plan?${search.toString()}`);
  },
  // 后端 specs 返回大写 kind（WALK_FORWARD/BOOTSTRAP…），前端域类型用小写
  // （ValidationKind）。在此归一，否则 MANUAL_KINDS 过滤会把全部 spec 滤掉，
  // 验证发起表单不渲染（E2E 隔离栈上实证的契约漂移）。
  listValidationSpecs: async () => {
    const specs = await request<ValidationSpec[]>("/api/v1/validation/specs");
    return specs.map((spec) => ({
      ...spec,
      kind: spec.kind.toLowerCase(),
    }));
  },
  getTrialStats: (id: string) =>
    request<TrialStats>(`/api/v1/strategies/${id}/trial-stats`),
  listValidation: (params?: { strategy_id?: string; kind?: string }) => {
    const search = new URLSearchParams();
    if (params?.strategy_id) search.set("strategy_id", params.strategy_id);
    if (params?.kind) search.set("kind", params.kind);
    const q = search.toString();
    return request<Page<ValidationRun> & { gates?: ValidationGates }>(
      `/api/v1/validation${q ? `?${q}` : ""}`,
    );
  },
  getValidationRun: (id: string) =>
    request<ValidationRun>(`/api/v1/validation/${id}`),
  getEvidence: (params: { strategy_id: string; strategy_version_id: string }) => {
    const search = new URLSearchParams({
      strategy_id: params.strategy_id,
      strategy_version_id: params.strategy_version_id,
    });
    return request<ValidationEvidence>(
      `/api/v1/validation/evidence?${search.toString()}`,
    );
  },
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
  createBootstrap: (body: {
    strategy_version_id: string;
    backtest_id?: string;
    n_boot?: number;
    confidence_level?: number;
    method?: "stationary" | "block";
    mean_block_length?: number;
    seed?: number;
  }) =>
    request<ValidationRun>("/api/v1/validation/bootstrap", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createRegime: (body: { strategy_version_id: string; backtest_id?: string }) =>
    request<ValidationRun>("/api/v1/validation/regime", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createSpa: (body: {
    strategy_version_id: string;
    backtest_id?: string;
    n_boot?: number;
    alpha?: number;
    seed?: number;
  }) =>
    request<ValidationRun>("/api/v1/validation/spa", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
