import { request } from "./http";
import type { ResearchNote, Page } from "./types";

export const researchApi = {
  listResearchNotes: (params?: { strategy_id?: string }) => {
    const search = new URLSearchParams();
    if (params?.strategy_id) search.set("strategy_id", params.strategy_id);
    const q = search.toString();
    return request<Page<ResearchNote>>(
      `/api/v1/research-notes${q ? `?${q}` : ""}`,
    );
  },
  getResearchNote: (id: string) =>
    request<ResearchNote>(`/api/v1/research-notes/${id}`),
  createResearchNote: (body: {
    strategy_id: string;
    strategy_version_id?: string;
    backtest_id?: string;
    title?: string;
    hypothesis?: string;
    method?: string;
    conclusion?: string;
    failure_modes?: string;
  }) =>
    request<ResearchNote>("/api/v1/research-notes", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateResearchNote: (
    id: string,
    body: {
      title?: string;
      hypothesis?: string;
      method?: string;
      conclusion?: string;
      failure_modes?: string;
      strategy_version_id?: string | null;
      backtest_id?: string | null;
    },
  ) =>
    request<ResearchNote>(`/api/v1/research-notes/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteResearchNote: (id: string) =>
    request<void>(`/api/v1/research-notes/${id}`, { method: "DELETE" }),
};
