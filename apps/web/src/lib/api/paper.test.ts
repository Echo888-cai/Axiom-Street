import { beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.hoisted(() => vi.fn());

vi.mock("./http", () => ({ request: requestMock }));

import { paperApi } from "./paper";

describe("paper API client", () => {
  beforeEach(() => requestMock.mockReset());

  it("posts an order and reads all paper state through strategy-scoped routes", async () => {
    requestMock.mockResolvedValue({});
    const strategyId = "strategy/1";
    const input = {
      strategy_id: strategyId,
      symbol: "SPY",
      side: "BUY" as const,
      quantity: 1,
      simulation_price: 100,
      client_order_id: "paper-1",
    };

    await paperApi.createOrder(input);
    await paperApi.listOrders(strategyId, 10);
    await paperApi.getPositions(strategyId);
    await paperApi.getReconciliation(strategyId);

    expect(requestMock).toHaveBeenNthCalledWith(1, "/api/v1/paper/orders", {
      method: "POST",
      body: JSON.stringify(input),
    });
    expect(requestMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/paper/orders?strategy_id=strategy%2F1&limit=10",
    );
    expect(requestMock).toHaveBeenNthCalledWith(
      3,
      "/api/v1/paper/positions?strategy_id=strategy%2F1",
    );
    expect(requestMock).toHaveBeenNthCalledWith(
      4,
      "/api/v1/paper/reconciliation?strategy_id=strategy%2F1",
    );
  });
});
