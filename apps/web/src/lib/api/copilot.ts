import { request } from "./http";
import type { CopilotContext } from "./types";

export const copilotApi = {
  getContext: (resource: "strategy" | "backtest", id: string) =>
    request<CopilotContext>(
      `/api/v1/copilot/context?resource=${resource}&id=${encodeURIComponent(id)}`,
    ),
};
