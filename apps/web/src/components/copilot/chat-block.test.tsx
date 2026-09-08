import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatBlock } from "./chat-block";
import type { CopilotChatMessage } from "@/lib/api/types";

const mocks = vi.hoisted(() => ({
  listChat: vi.fn(),
  chat: vi.fn(),
}));

vi.mock("@/lib/api/copilot", () => ({
  copilotApi: {
    listChat: mocks.listChat,
    chat: mocks.chat,
  },
}));

const STRATEGY_ID = "11111111-1111-4111-8111-111111111111";
const MESSAGE_ID = "22222222-2222-4222-8222-222222222222";

function message(overrides: Partial<CopilotChatMessage> = {}): CopilotChatMessage {
  return {
    id: MESSAGE_ID,
    strategy_id: STRATEGY_ID,
    resource: "strategy",
    resource_id: STRATEGY_ID,
    user_message: "该策略现在适合进入纸面交易吗?",
    assistant_message: "目前还不建议进入纸面交易,请先补齐验证闸门。",
    status: "DONE",
    model: "deepseek-v4-flash",
    error: null,
    duration_ms: 800,
    created_at: "2026-09-07T02:30:00Z",
    finished_at: "2026-09-07T02:30:00Z",
    ...overrides,
  };
}

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderBlock(
  props: Partial<React.ComponentProps<typeof ChatBlock>> = {},
) {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <ChatBlock
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

describe("ChatBlock", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listChat.mockResolvedValue([]);
    mocks.chat.mockResolvedValue({ status: "queued" });
  });

  it("renders a completed bounded conversation and quick prompts", async () => {
    mocks.listChat.mockResolvedValue([message()]);
    renderBlock();

    expect(await screen.findByText(/目前还不建议进入纸面交易/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "该停了吗?" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("只问研究判断,例如: 下一步该做什么?"))
      .toBeInTheDocument();
  });

  it("enqueues a quick prompt with the current research scope", async () => {
    renderBlock();

    const button = await screen.findByRole("button", { name: "该停了吗?" });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);

    await waitFor(() =>
      expect(mocks.chat).toHaveBeenCalledWith(
        "strategy",
        STRATEGY_ID,
        "基于当前试验和验证结果,现在该停了吗?",
      ),
    );
  });

  it("shows disabled privacy copy without querying the provider", async () => {
    renderBlock({ providerEnabled: false, providerName: "deepseek" });

    expect(await screen.findByText(/研究对话未启用/)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/只问研究判断/)).toBeNull();
    expect(mocks.listChat).not.toHaveBeenCalled();
  });

  it("shows a failed chat row honestly", async () => {
    mocks.listChat.mockResolvedValue([
      message({
        status: "FAILED",
        assistant_message: "",
        error: "模型服务暂时不可用",
      }),
    ]);
    renderBlock();

    expect(await screen.findByText("这次对话没有完成")).toBeInTheDocument();
    expect(screen.getByText(/模型服务暂时不可用/)).toBeInTheDocument();
  });
});
