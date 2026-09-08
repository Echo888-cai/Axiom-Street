import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RiskDesk } from "./risk-desk";
import type { RiskSummary, Strategy } from "@/lib/api/types";

const mocks = vi.hoisted(() => ({
  listStrategies: vi.fn(),
  getSummary: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ api: mocks }));

const strategy = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "趋势跟随",
  status: "PAPER",
} as unknown as Strategy;

const summary: RiskSummary = {
  strategy_id: strategy.id,
  strategy_status: "PAPER",
  risk_limits: { max_gross_leverage: 1.5 },
  risk_config_valid: true,
  account_available: true,
  initial_capital: 100000,
  cash: 70000,
  equity: 90000,
  gross_exposure: 0.2222,
  net_exposure: 0.2222,
  reconciliation_status: "MATCHED",
  blocking_reasons: [],
};

function renderDesk() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <RiskDesk />
    </QueryClientProvider>,
  );
}

describe("RiskDesk", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listStrategies.mockResolvedValue([strategy]);
    mocks.getSummary.mockResolvedValue(summary);
  });

  it("renders server-owned risk evidence without mutation controls", async () => {
    renderDesk();

    expect(await screen.findByText("风险配置有效")).toBeInTheDocument();
    expect(screen.getByText("90,000.00")).toBeInTheDocument();
    expect(screen.getByText("对账一致")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /保存|修改/ })).toBeNull();
  });

  it("renders blocking reasons from the server", async () => {
    mocks.getSummary.mockResolvedValue({
      ...summary,
      account_available: false,
      equity: null,
      blocking_reasons: ["paper_account_missing", "paper_reconciliation_not_matched"],
    });
    renderDesk();

    expect(await screen.findByText("尚未创建纸面账户")).toBeInTheDocument();
    expect(screen.getByText("纸面对账尚未匹配")).toBeInTheDocument();
  });
});
