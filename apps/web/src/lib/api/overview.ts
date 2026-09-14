import { request } from "./http";
import type { Overview } from "./types";

export const overviewApi = {
  getOverview: () => request<Overview>("/api/v1/overview"),
};
