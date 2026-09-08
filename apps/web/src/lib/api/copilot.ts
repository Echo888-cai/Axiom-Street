import { request } from "./http";
import type {
  CopilotContext,
  CopilotChatAccepted,
  CopilotChatMessage,
  CopilotInsight,
  CopilotSuggestAccepted,
  CopilotSuggestion,
  CopilotSuggestions,
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
  // P5-3: deterministic actionable cards (always available) + the optional
  // model priority pick over them (enqueue-only; poll getRecommendation).
  listSuggestions: (strategyId: string) =>
    request<CopilotSuggestions>(
      `/api/v1/copilot/suggestions?strategy_id=${encodeURIComponent(strategyId)}`,
    ),
  suggest: (resource: CopilotResource, id: string) =>
    request<CopilotSuggestAccepted>("/api/v1/copilot/suggest", {
      method: "POST",
      body: JSON.stringify({ resource, id }),
    }),
  getRecommendation: (strategyId: string) =>
    request<CopilotSuggestion | null>(
      `/api/v1/copilot/suggestions/recommendation?strategy_id=${encodeURIComponent(strategyId)}`,
    ),
  listChat: (strategyId: string, limit = 30) =>
    request<CopilotChatMessage[]>(
      `/api/v1/copilot/chat?strategy_id=${encodeURIComponent(strategyId)}&limit=${limit}`,
    ),
  chat: (resource: CopilotResource, id: string, message: string) =>
    request<CopilotChatAccepted>("/api/v1/copilot/chat", {
      method: "POST",
      body: JSON.stringify({ resource, id, message }),
    }),
};
