import { request } from "./http";
import type { TrialStats, ValidationRun } from "./types";

export const validationApi = {
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
  getValidationRun: (id: string) =>
    request<ValidationRun>(`/api/v1/validation/${id}`),
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
