import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PaperDesk } from "./paper-desk";
import type { PaperPositions, Strategy } from "@/lib/api/types";

const mocks = vi.hoisted(() => ({
  listStrategies: vi.fn(),
  createOrder: vi.fn(),
  listOrders: vi.fn(),
  getPositions: vi.fn(),
  getReconciliation: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ api: mocks }));

const strategy = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "趋势跟随",
  description: null,
  status: "PAPER",
  asset_class: "equity",
  benchmark: "SPY",
  family_id: null,
  latest_version: null,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
} as unknown as Strategy;

const emptyPositions: PaperPositions = { account: null, positions: [] };

function renderDesk() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <PaperDesk />
    </QueryClientProvider>,
  );
}

describe("PaperDesk", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listStrategies.mockResolvedValue([strategy]);
    mocks.createOrder.mockResolvedValue({ status: "queued" });
    mocks.listOrders.mockResolvedValue([]);
    mocks.getPositions.mockResolvedValue(emptyPositions);
    mocks.getReconciliation.mockResolvedValue(null);
  });

  it("submits a real paper order for the selected strategy", async () => {
    renderDesk();

    expect(await screen.findByText("趋势跟随")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("标的"), { target: { value: "SPY" } });
    fireEvent.change(screen.getByLabelText("数量"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("模拟价格"), {
      target: { value: "100" },
    });
    fireEvent.click(screen.getByRole("button", { name: "提交订单" }));

    await waitFor(() =>
      expect(mocks.createOrder).toHaveBeenCalledWith(
        expect.objectContaining({
          strategy_id: strategy.id,
          symbol: "SPY",
          side: "BUY",
          quantity: 2,
          simulation_price: 100,
        }),
      ),
    );
    expect(await screen.findByText("订单已排队")).toBeInTheDocument();
  });

  it("shows an honest empty state when no paper account exists", async () => {
    renderDesk();

    expect(await screen.findByText("尚未创建纸面账户")).toBeInTheDocument();
    expect(screen.getByText(/提交第一笔订单后/)).toBeInTheDocument();
  });
});
