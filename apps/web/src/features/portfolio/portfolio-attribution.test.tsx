import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PortfolioAttribution } from "./portfolio-attribution";
import { api } from "@/lib/api";
import type {
  Portfolio,
  PortfolioAllocation,
  PortfolioAttribution as PortfolioAttributionRow,
} from "@/lib/api/types";

const mocks = vi.hoisted(() => ({
  listPortfolios: vi.fn(),
  listPortfolioAllocations: vi.fn(),
  listPortfolioAttribution: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    listPortfolios: mocks.listPortfolios,
    listPortfolioAllocations: mocks.listPortfolioAllocations,
    listPortfolioAttribution: mocks.listPortfolioAttribution,
  },
}));

const portfolio: Portfolio = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "核心多策略",
  base_currency: "USD",
  status: "ACTIVE",
  initial_capital: 100000,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

const allocation: PortfolioAllocation = {
  id: "22222222-2222-4222-8222-222222222222",
  portfolio_id: portfolio.id,
  strategy_id: "33333333-3333-4333-8333-333333333333",
  weight: 0.6,
  effective_from: "2026-09-01",
  effective_to: null,
  created_at: "2026-09-01T00:00:00Z",
};

const attribution: PortfolioAttributionRow = {
  id: "44444444-4444-4444-8444-444444444444",
  portfolio_id: portfolio.id,
  as_of: "2026-09-07",
  portfolio_return: 0.08,
  benchmark_return: 0.05,
  allocation_effect: 0.01,
  selection_effect: 0.015,
  interaction_effect: 0.005,
  active_return: 0.03,
  inputs: {},
  created_at: "2026-09-07T00:00:00Z",
};

function renderPage() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false } },
        })
      }
    >
      <PortfolioAttribution />
    </QueryClientProvider>,
  );
}

describe("PortfolioAttribution", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listPortfolios).mockResolvedValue([portfolio]);
    vi.mocked(api.listPortfolioAllocations).mockResolvedValue([allocation]);
    vi.mocked(api.listPortfolioAttribution).mockResolvedValue([attribution]);
  });

  it("renders server-owned allocation and attribution evidence", async () => {
    renderPage();

    expect(await screen.findByText("核心多策略")).toBeInTheDocument();
    expect(await screen.findByText("60.0%")).toBeInTheDocument();
    expect(await screen.findByText("+3.00%")).toBeInTheDocument();
    expect(screen.getByText("配置效应")).toBeInTheDocument();
    expect(screen.getByText("选择效应")).toBeInTheDocument();
    expect(screen.getByText("交互效应")).toBeInTheDocument();
    expect(
      screen.getByText(/因子暴露尚未接入/),
    ).toBeInTheDocument();
  });

  it("shows an honest empty state when no portfolio exists", async () => {
    vi.mocked(api.listPortfolios).mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("还没有组合")).toBeInTheDocument();
    expect(screen.getByText(/先创建一个组合/)).toBeInTheDocument();
    expect(api.listPortfolioAllocations).not.toHaveBeenCalled();
  });
});
