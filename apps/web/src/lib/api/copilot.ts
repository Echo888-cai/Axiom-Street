import { request } from "./http";
import type {
  CopilotContext,
  CopilotInsight,
  CopilotSynthesizeAccepted,
} from "./types";

export type CopilotResource = "strategy" | "backtest";

export const copilotApi = {
  getContext: (resource: CopilotResource, id: string) =>
    request<CopilotContext>(
      `/api/v1/copilot/context?resource=${resource}&id=${encodeURIComponent(id)}`,
    ),
  // P5-2: enqueue one model synthesize pass; the worker calls DeepSeek and
  // records the ledger row (poll listInsights until the head row changes).
  synthesize: (resource: CopilotResource, id: string) =>
    request<CopilotSynthesizeAccepted>("/api/v1/copilot/synthesize", {
      method: "POST",
      body: JSON.stringify({ resource, id }),
    }),
  listInsights: (strategyId: string) =>
    request<CopilotInsight[]>(
      `/api/v1/copilot/insights?strategy_id=${encodeURIComponent(strategyId)}`,
    ),
};
