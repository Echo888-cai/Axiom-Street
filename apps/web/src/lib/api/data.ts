import { request, API_URL } from "./http";
import type { IngestJob, DataSnapshot, DataStatus } from "./types";

export const dataApi = {
  health: () => request<{ status: string; version: string }>("/health"),
  dataStatus: () => request<DataStatus>("/api/v1/data/status"),
  reconcileMarket: (force = false) =>
    request<{
      ok: boolean;
      skipped: boolean;
      job: IngestJob;
      symbols: string[];
    }>(`/api/v1/data/reconcile?force=${force ? "true" : "false"}`, {
      method: "POST",
    }),
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
};
