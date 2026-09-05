import { request, unwrapList } from "./http";
import type { Page, UniverseMember, Universe } from "./types";

export const universesApi = {
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
      applied: Array<{
        universe_id: string;
        symbol: string;
        effective_to: string;
      }>;
      skipped: Array<{ universe_id: string; symbol: string; reason?: string }>;
      errors: Array<{ universe_id?: string; symbol?: string; message: string }>;
      inferred?: Array<{
        symbol: string;
        last_bar: string;
        effective_to: string;
      }>;
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
