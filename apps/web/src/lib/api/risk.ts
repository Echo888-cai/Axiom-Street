import { request } from "./http";
import type { RiskSummary } from "./types";

export const riskApi = {
  getSummary: (strategyId: string) =>
    request<RiskSummary>(
      `/api/v1/risk/summary?strategy_id=${encodeURIComponent(strategyId)}`,
    ),
};
