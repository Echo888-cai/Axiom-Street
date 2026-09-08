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
});
