import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePathname } from "next/navigation";
import { CopilotPanel } from "./copilot-panel";
import { copilotApi } from "@/lib/api/copilot";
import type { CopilotContext } from "@/lib/api/types";

vi.mock("next/navigation", () => ({ usePathname: vi.fn(() => "/") }));

vi.mock("@/lib/api/copilot", () => ({
  copilotApi: { getContext: vi.fn() },
}));

const STRATEGY_ID = "11111111-1111-4111-8111-111111111111";
const OLD_SNAPSHOT = "spy-daily-20260831-1209a3";
const NEW_SNAPSHOT = "spy-daily-20260901-1209a3";

const context: CopilotContext = {
  resource: "strategy",
  strategy_id: STRATEGY_ID,
  strategy_name: "SPY 200DMA",
  strategy_status: "BACKTESTED",
  family_id: STRATEGY_ID,
  latest_version: 2,
  total_trials: 4,
  by_snapshot: [
    {
      data_snapshot_id: "22222222-2222-4222-8222-222222222222",
      snapshot_key: OLD_SNAPSHOT,
      superseded_by_key: NEW_SNAPSHOT,
      count: 3,
      duplicate_parameter_hashes: 1,
    },
    {
      data_snapshot_id: "33333333-3333-4333-8333-333333333333",
      snapshot_key: NEW_SNAPSHOT,
      superseded_by_key: null,
      count: 1,
      duplicate_parameter_hashes: 0,
    },
  ],
  gates: [
    { kind: "DSR", status: "COMPLETED", passed: true, finished_at: "2026-09-01T00:00:00Z" },
    { kind: "PBO", status: "COMPLETED", passed: false, finished_at: "2026-09-02T00:00:00Z" },
  ],
  backtest: null,
  provider: { name: "noop", enabled: false },
};

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderPanel() {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <CopilotPanel />
    </QueryClientProvider>,
  );
}

describe("CopilotPanel", () => {
  beforeEach(() => {
    vi.mocked(usePathname).mockReturnValue(`/strategies/${STRATEGY_ID}`);
    vi.mocked(copilotApi.getContext).mockReset();
    vi.mocked(copilotApi.getContext).mockResolvedValue(context);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders deterministic facts for the strategy on the detail page", async () => {
    renderPanel();

    expect(await screen.findByText("SPY 200DMA")).toBeInTheDocument();
    expect(screen.getByText("BACKTESTED")).toBeInTheDocument();
    expect(screen.getByText("版本 2")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("重复参数 1")).toBeInTheDocument();
    expect(screen.getByText("已被新快照取代")).toBeInTheDocument();
    // Gate summary: DSR passed, PBO failed (both COMPLETED).
    expect(screen.getByText("Deflated Sharpe Ratio（去偿夏普）")).toBeInTheDocument();
    expect(screen.getAllByText("未通过")).toHaveLength(1);
    expect(screen.getByText("通过")).toBeInTheDocument();
    // Honest footer.
    expect(screen.getByText("只读事实 · AI 不改动研究状态")).toBeInTheDocument();

    expect(copilotApi.getContext).toHaveBeenCalledWith("strategy", STRATEGY_ID);
  });

  it("renders the honest empty state on pages without a research context", async () => {
    vi.mocked(usePathname).mockReturnValue("/validation");

    renderPanel();

    expect(await screen.findByText("此页面没有研究上下文")).toBeInTheDocument();
    expect(copilotApi.getContext).not.toHaveBeenCalled();
  });

  it("renders the not-found empty state when the context fetch fails", async () => {
    vi.mocked(copilotApi.getContext).mockRejectedValue(new Error("策略不存在"));

    renderPanel();

    expect(await screen.findByText("无法读取研究上下文")).toBeInTheDocument();
  });
});
