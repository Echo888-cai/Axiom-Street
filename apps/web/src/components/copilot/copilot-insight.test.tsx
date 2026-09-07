import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InsightBlock } from "./copilot-insight";
import type { CopilotInsight } from "@/lib/api/types";

const mocks = vi.hoisted(() => ({
  listInsights: vi.fn(),
  synthesize: vi.fn(),
}));

vi.mock("@/lib/api/copilot", () => ({
  copilotApi: {
    getContext: vi.fn(),
    listInsights: mocks.listInsights,
    synthesize: mocks.synthesize,
  },
}));

const STRATEGY_ID = "11111111-1111-4111-8111-111111111111";
const INSIGHT_ID = "22222222-2222-4222-8222-222222222222";

function doneRow(overrides: Partial<CopilotInsight> = {}): CopilotInsight {
  return {
    id: INSIGHT_ID,
    strategy_id: STRATEGY_ID,
    status: "DONE",
    model: "deepseek-v4-flash",
    narrative: "在这份 20260831 快照上你已经试了 47 次,别继续了。",
    error: null,
    duration_ms: 812,
    created_at: "2026-09-07T02:30:00Z",
    finished_at: "2026-09-07T02:30:00Z",
    ...overrides,
  };
}

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderBlock(props: Partial<React.ComponentProps<typeof InsightBlock>> = {}) {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <InsightBlock
        resource="strategy"
        id={STRATEGY_ID}
        strategyId={STRATEGY_ID}
        providerEnabled
        providerName="deepseek"
        pollMs={20}
        {...props}
      />
    </QueryClientProvider>,
  );
}

async function clickEvaluate(label: string | RegExp) {
  const button = await screen.findByRole("button", { name: label });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
}

describe("InsightBlock", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listInsights.mockResolvedValue([]);
    mocks.synthesize.mockResolvedValue({ status: "queued" });
  });

  it("stays silent and honest when the provider is disabled", async () => {
    mocks.listInsights.mockResolvedValue([]);
    renderBlock({ providerEnabled: false, providerName: "deepseek" });

    expect(await screen.findByText(/模型评估未启用/)).toBeInTheDocument();
    expect(mocks.listInsights).not.toHaveBeenCalled();
  });

  it("shows the idle state with an evaluate action when there is no row", async () => {
    renderBlock();

    expect(await screen.findByText(/还没有评估记录/)).toBeInTheDocument();
    expect(mocks.listInsights).toHaveBeenCalledWith(STRATEGY_ID);
  });

  it("enqueues a synthesize on click and shows the new narrative when it lands", async () => {
    mocks.listInsights
      .mockResolvedValueOnce([])
      .mockResolvedValue([doneRow()]);
    renderBlock();

    await clickEvaluate("让 Copilot 评估一下");

    expect(mocks.synthesize).toHaveBeenCalledWith("strategy", STRATEGY_ID);
    expect(await screen.findByText(/47 次,别继续了/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "让 Copilot 评估一下" })).toBeNull();
    expect(
      screen.getByRole("button", { name: "重新评估" }),
    ).toBeInTheDocument();
  });

  it("shows a failed ledger row with a retry action", async () => {
    mocks.listInsights.mockResolvedValue([
      doneRow({
        status: "FAILED",
        narrative: "",
        error: "DeepSeek 账户余额不足(402),模型评估已停止",
      }),
    ]);
    renderBlock();

    expect(await screen.findByText("这次评估失败了")).toBeInTheDocument();
    expect(screen.getByText(/余额不足/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
  });

  it("surfaces a failed enqueue without getting stuck", async () => {
    mocks.synthesize.mockRejectedValue(new Error("模型未启用:未配置 API key"));
    renderBlock();

    await clickEvaluate("让 Copilot 评估一下");

    expect(await screen.findByText(/未配置 API key/)).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "让 Copilot 评估一下" }),
      ).toBeEnabled(),
    );
  });
});
