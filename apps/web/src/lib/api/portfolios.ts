import { request } from "./http";
import type {
  Portfolio,
  PortfolioAllocation,
  PortfolioAttribution,
} from "./types";

export const portfoliosApi = {
  listPortfolios: () => request<Portfolio[]>("/api/v1/portfolios"),
  listPortfolioAllocations: (portfolioId: string) =>
    request<PortfolioAllocation[]>(
      `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/allocations`,
    ),
  listPortfolioAttribution: (portfolioId: string, limit = 30) =>
    request<PortfolioAttribution[]>(
      `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/attribution?limit=${limit}`,
    ),
};
