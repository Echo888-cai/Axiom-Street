import { request } from "./http";
import type {
  Portfolio,
  PortfolioAllocation,
  PortfolioAttribution,
} from "./types";

export type FactorRegressionRecord = {
  id: string;
  portfolio_id: string;
  window_start?: string | null;
  window_end?: string | null;
  model: string;
  source: string;
  frequency: string;
  alpha: number;
  r2: number;
  n_obs: number;
  exposures: Record<string, number>;
  created_at: string;
};

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
  // P3.4 因子台账与多期归因
  listFactorRegressions: (portfolioId: string) =>
    request<FactorRegressionRecord[]>(
      `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/factor-regressions`,
    ),
  createFactorRegression: (
    portfolioId: string,
    body: {
      model?: string;
      source?: string;
      frequency?: string;
      window_start?: string | null;
      window_end?: string | null;
      n_obs: number;
      alpha?: number;
      r2?: number;
      exposures: Record<string, number>;
    },
  ) =>
    request<FactorRegressionRecord>(
      `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/factor-regressions`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  linkMultiPeriodAttribution: (
    portfolioId: string,
    body: {
      periods: Array<{
        period: string;
        observations: Array<{
          strategy_id: string;
          weight: number;
          strategy_return: number;
          benchmark_return: number;
        }>;
      }>;
    },
  ) =>
    request<MultiPeriodLinkResult>(
      `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/attribution/link`,
      { method: "POST", body: JSON.stringify(body) },
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

export type MultiPeriodLinkResult = {
  linked_active: number;
  linked_allocation: number;
  linked_selection: number;
  linked_interaction: number;
  residual: number;
  residual_explained: string;
  strategy_effects: Record<string, Record<string, number>>;
};

