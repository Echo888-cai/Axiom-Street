import { beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.hoisted(() => vi.fn());

vi.mock("./http", () => ({ request: requestMock }));

import { portfoliosApi } from "./portfolios";

describe("portfolio API client", () => {
  beforeEach(() => requestMock.mockReset());

  it("keeps portfolio reads on the typed backend routes", async () => {
    requestMock.mockResolvedValue([]);

    await portfoliosApi.listPortfolios();
    await portfoliosApi.listPortfolioAllocations("portfolio/1");
    await portfoliosApi.listPortfolioAttribution("portfolio/1", 10);

    expect(requestMock).toHaveBeenNthCalledWith(1, "/api/v1/portfolios");
    expect(requestMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/portfolios/portfolio%2F1/allocations",
    );
    expect(requestMock).toHaveBeenNthCalledWith(
      3,
      "/api/v1/portfolios/portfolio%2F1/attribution?limit=10",
    );
  });

  it("writes a portfolio, allocation, and attribution through typed routes", async () => {
    requestMock.mockResolvedValue({});

    const portfolioId = "portfolio/1";
    await portfoliosApi.createPortfolio({
      name: "核心组合",
      base_currency: "USD",
      initial_capital: 100000,
    });
    await portfoliosApi.createAllocation(portfolioId, {
      strategy_id: "strategy/1",
      weight: 0.6,
      effective_from: "2026-09-01",
    });
    await portfoliosApi.createAttribution(portfolioId, {
      as_of: "2026-09-07",
      returns: [
        {
          strategy_id: "strategy/1",
          strategy_return: 0.04,
          benchmark_return: 0.02,
        },
      ],
    });

    expect(requestMock).toHaveBeenNthCalledWith(2, "/api/v1/portfolios/portfolio%2F1/allocations", {
      method: "POST",
      body: JSON.stringify({
        strategy_id: "strategy/1",
        weight: 0.6,
        effective_from: "2026-09-01",
      }),
    });
    expect(requestMock).toHaveBeenNthCalledWith(3, "/api/v1/portfolios/portfolio%2F1/attribution", {
      method: "POST",
      body: JSON.stringify({
        as_of: "2026-09-07",
        returns: [
          {
            strategy_id: "strategy/1",
            strategy_return: 0.04,
            benchmark_return: 0.02,
          },
        ],
      }),
    });
  });
});
