import { request, API_URL } from "./http";
import type { IngestJob, DataSnapshot, DataStatus } from "./types";

export type CapabilityProbeReason = { code: string; message: string; detail?: string };
export type CapabilityProbe = {
  provider: string;
  symbol: string;
  capabilities: Record<"price" | "dividends" | "splits", CapabilityProbeReason>;
};
export type DataCatalog = {
  data_root: string;
  declared_capabilities: Record<string, boolean> | null;
  snapshot_count: number;
  snapshots: Array<{
    snapshot_key: string;
    created_at: string | null;
    symbols: string[];
    frequency: string;
    timezone: string;
    adjustment: string;
    range: { start: string | null; end: string | null };
    row_count: number | null;
    corporate_actions_verified: boolean;
    gaps: Array<{ rule: string; severity: string; message?: string }>;
    prior_snapshot_key: string | null;
  }>;
};

export const dataApi = {
  dataStatus: () => request<DataStatus>("/api/v1/data/status"),
  // P3.1 数据目录与权限探测
  dataCatalog: () => request<DataCatalog>("/api/v1/data/catalog"),
  probeCapabilities: (body: { provider?: string; symbol?: string }) =>
    request<CapabilityProbe>("/api/v1/data/capabilities/probe", {
      method: "POST",
      body: JSON.stringify(body),
    }),
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
