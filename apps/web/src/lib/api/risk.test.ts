import { beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.hoisted(() => vi.fn());

vi.mock("./http", () => ({ request: requestMock }));

import { riskApi } from "./risk";

describe("risk API client", () => {
  beforeEach(() => requestMock.mockReset());

  it("reads a strategy-scoped server-owned risk summary", async () => {
    requestMock.mockResolvedValue({});

    await riskApi.getSummary("strategy/1");

    expect(requestMock).toHaveBeenCalledWith(
      "/api/v1/risk/summary?strategy_id=strategy%2F1",
    );
  });
});
