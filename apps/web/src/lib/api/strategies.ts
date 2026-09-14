import { request, unwrapList } from "./http";
import type { Strategy, StrategyVersion, Page } from "./types";

export const strategiesApi = {
  listStrategyPage: (params?: {
    q?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.q?.trim()) search.set("q", params.q.trim());
    if (params?.status && params.status !== "ALL") search.set("status", params.status);
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    const q = search.toString();
    return request<Page<Strategy>>(`/api/v1/strategies${q ? `?${q}` : ""}`);
  },
  listStrategies: () =>
    strategiesApi
      .listStrategyPage({})
      .then((page) => unwrapList<Strategy>(page)),
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
