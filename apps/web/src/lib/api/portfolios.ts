import { request } from "./http";
import type {
  Portfolio,
  PortfolioAllocation,
  PortfolioAttribution,
} from "./types";

export const portfoliosApi = {
  listPortfolios: () => request<Portfolio[]>("/api/v1/portfolios"),
  createPortfolio: (body: {
    name: string;
    base_currency: string;
    initial_capital: number;
  }) =>
    request<Portfolio>("/api/v1/portfolios", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createAllocation: (
    portfolioId: string,
    body: {
      strategy_id: string;
      weight: number;
      effective_from: string;
      effective_to?: string | null;
    },
  ) =>
    request<PortfolioAllocation>(
      `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/allocations`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
  createAttribution: (
    portfolioId: string,
    body: {
      as_of: string;
      returns: Array<{
        strategy_id: string;
        strategy_return: number;
        benchmark_return: number;
      }>;
    },
  ) =>
    request<PortfolioAttribution>(
      `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/attribution`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
  listPortfolioAllocations: (portfolioId: string) =>
    request<PortfolioAllocation[]>(
      `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/allocations`,
    ),
  listPortfolioAttribution: (portfolioId: string, limit = 30) =>
    request<PortfolioAttribution[]>(
      `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/attribution?limit=${limit}`,
    ),
};
