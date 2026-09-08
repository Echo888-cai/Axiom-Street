import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PortfolioAttribution } from "./portfolio-attribution";
import { api } from "@/lib/api";
import type {
  Portfolio,
  PortfolioAllocation,
  PortfolioAttribution as PortfolioAttributionRow,
  Strategy,
} from "@/lib/api/types";

const mocks = vi.hoisted(() => ({
  listPortfolios: vi.fn(),
  listPortfolioAllocations: vi.fn(),
  listPortfolioAttribution: vi.fn(),
  createPortfolio: vi.fn(),
  createAllocation: vi.fn(),
  createAttribution: vi.fn(),
  listStrategies: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    listPortfolios: mocks.listPortfolios,
    listPortfolioAllocations: mocks.listPortfolioAllocations,
    listPortfolioAttribution: mocks.listPortfolioAttribution,
    createPortfolio: mocks.createPortfolio,
    createAllocation: mocks.createAllocation,
    createAttribution: mocks.createAttribution,
    listStrategies: mocks.listStrategies,
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
    vi.mocked(api.createPortfolio).mockResolvedValue(portfolio);
    vi.mocked(api.createAllocation).mockResolvedValue(allocation);
    vi.mocked(api.createAttribution).mockResolvedValue(attribution);
    vi.mocked(api.listStrategies).mockResolvedValue([]);
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

  it("creates a portfolio from the empty state form", async () => {
    vi.mocked(api.listPortfolios).mockResolvedValue([]);
    renderPage();

    await screen.findByText("还没有组合");
    fireEvent.change(screen.getByLabelText("组合名称"), { target: { value: "新组合" } });
    fireEvent.change(screen.getByLabelText("初始资金"), { target: { value: "50000" } });
    fireEvent.click(screen.getByRole("button", { name: "创建组合" }));

    await waitFor(() =>
      expect(mocks.createPortfolio).toHaveBeenCalledWith({
        name: "新组合",
        base_currency: "USD",
        initial_capital: 50000,
      }),
    );
    expect(await screen.findByText("组合已创建")).toBeInTheDocument();
  });

  it("submits an allocation and shows the server-owned weight total", async () => {
    vi.mocked(api.listStrategies).mockResolvedValue([
      {
        ...portfolio,
        id: "55555555-5555-4555-8555-555555555555",
        name: "趋势策略",
      } as unknown as Strategy,
    ]);
    renderPage();

    expect(await screen.findByText("核心多策略")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("配置策略"), {
      target: { value: "55555555-5555-4555-8555-555555555555" },
    });
    fireEvent.change(screen.getByLabelText("配置权重"), { target: { value: "0.4" } });
    fireEvent.change(screen.getByLabelText("生效日期"), { target: { value: "2026-09-08" } });
    fireEvent.click(screen.getByRole("button", { name: "添加配置" }));

    await waitFor(() =>
      expect(mocks.createAllocation).toHaveBeenCalledWith(portfolio.id, {
        strategy_id: "55555555-5555-4555-8555-555555555555",
        weight: 0.4,
        effective_from: "2026-09-08",
      }),
    );
    expect(screen.getByText(/当前权重合计/)).toBeInTheDocument();
  });

  it("submits returns without sending allocation weights to the attribution API", async () => {
    vi.mocked(api.listStrategies).mockResolvedValue([
      {
        ...portfolio,
        id: allocation.strategy_id,
        name: "趋势策略",
      } as unknown as Strategy,
    ]);
    renderPage();

    expect(await screen.findByText("核心多策略")).toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText("归因日期"), {
      target: { value: "2026-09-07" },
    });
    fireEvent.change(await screen.findByLabelText(/策略收益/), { target: { value: "0.04" } });
    fireEvent.change(await screen.findByLabelText(/基准收益/), { target: { value: "0.02" } });
    fireEvent.click(screen.getByRole("button", { name: "提交归因" }));

    await waitFor(() => expect(mocks.createAttribution).toHaveBeenCalledTimes(1));
    const body = mocks.createAttribution.mock.calls[0][1];
    expect(body).toEqual({
      as_of: "2026-09-07",
      returns: [
        {
          strategy_id: allocation.strategy_id,
          strategy_return: 0.04,
          benchmark_return: 0.02,
        },
      ],
    });
    expect(body.returns[0]).not.toHaveProperty("weight");
  });
});
