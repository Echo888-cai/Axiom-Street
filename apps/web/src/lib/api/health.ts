import { request } from "./http";
import type { HealthStatus } from "./types";

export const healthApi = {
  health: () => request<HealthStatus>("/health"),
};
