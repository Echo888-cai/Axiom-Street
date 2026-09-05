import { request, unwrapList } from "./http";
import type { Strategy, StrategyVersion, Page } from "./types";

export const strategiesApi = {
  listStrategies: () =>
    request<Page<Strategy> | Strategy[]>("/api/v1/strategies").then(unwrapList),
  getStrategy: (id: string) => request<Strategy>(`/api/v1/strategies/${id}`),
  updateStrategy: (id: string, body: { name?: string; description?: string }) =>
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
    body: {
      code: string;
      config?: Record<string, unknown>;
      commit_message?: string;
    },
  ) =>
    request<StrategyVersion>(`/api/v1/strategies/${strategyId}/versions`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listVersions: (strategyId: string) =>
    request<StrategyVersion[]>(`/api/v1/strategies/${strategyId}/versions`),
  deleteStrategy: (id: string) =>
    request<void>(`/api/v1/strategies/${id}`, { method: "DELETE" }),
};
