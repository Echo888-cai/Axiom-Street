import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ActionsBlock } from "./actions-block";
import type { CopilotSuggestion, CopilotSuggestionCard } from "@/lib/api/types";

const mocks = vi.hoisted(() => ({
  listSuggestions: vi.fn(),
  suggest: vi.fn(),
  getRecommendation: vi.fn(),
  postValidation: vi.fn(),
}));

vi.mock("@/lib/api/copilot", () => ({
  copilotApi: {
    listSuggestions: mocks.listSuggestions,
    suggest: mocks.suggest,
    getRecommendation: mocks.getRecommendation,
  },
}));

vi.mock("@/lib/api/http", () => ({
  request: mocks.postValidation,
}));

const STRATEGY_ID = "11111111-1111-4111-8111-111111111111";
const VERSION_ID = "22222222-2222-4222-8222-222222222222";
const BACKTEST_ID = "33333333-3333-4333-8333-333333333333";
const RUN_ID = "44444444-4444-4444-8444-444444444444";

function runCard(overrides: Partial<CopilotSuggestionCard> = {}): CopilotSuggestionCard {
  return {
    key: "run_validation:PBO",
    action: "run_validation",
    executable: true,
    validation_kind: "PBO",
    strategy_version_id: VERSION_ID,
    target_version: 1,
    template_backtest_id: BACKTEST_ID,
    params: { values: [100, 150, 200, 250, 300] },
    reason_code: "never_run",
    ...overrides,
  };
}

function guideCard(): CopilotSuggestionCard {
  return {
    key: "guide:backtest_first",
    action: "guide",
    executable: false,
    validation_kind: null,
    strategy_version_id: VERSION_ID,
    target_version: 1,
    template_backtest_id: null,
    params: {},
    reason_code: "backtest_first",
  };
}

function disciplineCard(): CopilotSuggestionCard {
  return {
    key: "discipline:superseded_snapshot",
    action: "discipline",
    executable: false,
    validation_kind: null,
    strategy_version_id: null,
    target_version: null,
    template_backtest_id: null,
    params: {},
    reason_code: "superseded_snapshot",
  };
}

function doneRun(): CopilotSuggestion {
  return {
    id: RUN_ID,
    strategy_id: STRATEGY_ID,
    status: "DONE",
    model: "deepseek-v4-flash",
    picked_id: "run_validation:PBO",
    reason: "先把 PBO 闸门补上,别再重复试同一参数。",
    error: null,
    duration_ms: 800,
    created_at: "2026-09-07T02:30:00Z",
    finished_at: "2026-09-07T02:30:00Z",
  };
}

function failedRun(): CopilotSuggestion {
  return {
    id: RUN_ID,
    strategy_id: STRATEGY_ID,
    status: "FAILED",
    model: "deepseek-v4-flash",
    picked_id: null,
    reason: "",
    error: "DeepSeek API key 无效(401)",
    duration_ms: 5,
    created_at: "2026-09-07T02:30:00Z",
    finished_at: "2026-09-07T02:30:00Z",
  };
}

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderBlock(
  cards: CopilotSuggestionCard[],
  props: Partial<React.ComponentProps<typeof ActionsBlock>> = {},
) {
  mocks.listSuggestions.mockResolvedValue({ candidates: cards });
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <ActionsBlock
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

async function clickRank() {
  const button = await screen.findByRole("button", { name: "让 Copilot 排序" });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
}

describe("ActionsBlock", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.suggest.mockResolvedValue({ status: "queued" });
    mocks.getRecommendation.mockResolvedValue(null);
    mocks.postValidation.mockResolvedValue({
      id: RUN_ID,
      strategy_id: STRATEGY_ID,
      strategy_version_id: VERSION_ID,
      backtest_id: BACKTEST_ID,
      kind: "PBO",
      status: "QUEUED",
      progress_step: "Queued",
      params: {},
      result: {},
      passed: false,
      created_at: "2026-09-07T02:30:00Z",
    });
  });

  it("shows an honest empty state when there are no cards", async () => {
    renderBlock([]);

    expect(await screen.findByText("当前没有可建议的动作")).toBeInTheDocument();
    expect(mocks.listSuggestions).toHaveBeenCalledWith(STRATEGY_ID);
  });

  it("renders a runnable gate card with an adopt action", async () => {
    renderBlock([runCard()]);

    expect(await screen.findByText(/PBO/)).toBeInTheDocument();
    expect(screen.getByText("该闸门在最新版本上还没跑过")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "采纳" })).toBeInTheDocument();
  });

  it("renders guide and discipline cards without adopt actions", async () => {
    renderBlock([guideCard(), disciplineCard()]);

    expect(
      await screen.findByText(/先跑一条,补闸门建议才会出现/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/部分试验仍留在已被新快照取代的数据快照上/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "采纳" })).toBeNull();
  });

  it("adopting a card posts the exact validation payload", async () => {
    renderBlock([runCard()]);

    fireEvent.click(await screen.findByRole("button", { name: "采纳" }));
    expect(await screen.findByText("采纳这条建议?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "提交验证" }));

    await waitFor(() =>
      expect(mocks.postValidation).toHaveBeenCalledWith(
        "/api/v1/validation",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            kind: "PBO",
            strategy_version_id: VERSION_ID,
            backtest_id: BACKTEST_ID,
            params: { values: [100, 150, 200, 250, 300] },
          }),
        }),
      ),
    );
  });

  it("hides the model-ranking control when the provider is disabled", async () => {
    renderBlock([runCard()], { providerEnabled: false, providerName: "deepseek" });

    await screen.findByText(/PBO/);
    expect(screen.queryByRole("button", { name: "让 Copilot 排序" })).toBeNull();
    expect(mocks.getRecommendation).not.toHaveBeenCalled();
  });

  it("enqueues a ranking and shows the model pick when it lands", async () => {
    mocks.getRecommendation
      .mockResolvedValueOnce(null)
      .mockResolvedValue(doneRun());
    renderBlock([runCard()]);

    await clickRank();

    await waitFor(() => expect(mocks.suggest).toHaveBeenCalledWith("strategy", STRATEGY_ID));
    expect(await screen.findByText(/先把 PBO 闸门补上/)).toBeInTheDocument();
  });

  it("shows an honest failure when ranking failed", async () => {
    mocks.getRecommendation
      .mockResolvedValueOnce(null)
      .mockResolvedValue(failedRun());
    renderBlock([runCard()]);

    await clickRank();

    expect(await screen.findByText("这次没有生成优先建议")).toBeInTheDocument();
    expect(screen.getByText(/401/)).toBeInTheDocument();
  });
});
