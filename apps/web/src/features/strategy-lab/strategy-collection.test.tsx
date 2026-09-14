import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import StrategyCollection from "./strategy-collection";
import type { Strategy } from "@/lib/api";

vi.mock("@/lib/api", async (original) => {
  const actual = await original<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: { ...actual.api, listStrategyPage: vi.fn(), getOverview: vi.fn() },
  };
});

import { api } from "@/lib/api";

function strategy(id: string, name: string): Strategy {
  return {
    id,
    name,
    description: "",
    status: "DRAFT",
    benchmark: "SPY",
    latest_version: { id: `v-${id}`, version: 1 },
    updated_at: "2026-09-14T00:00:00",
  } as unknown as Strategy;
}

function show() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <StrategyCollection />
    </QueryClientProvider>,
  );
}

describe("StrategyCollection pagination", () => {
  beforeEach(() => {
    vi.mocked(api.getOverview).mockResolvedValue({
      strategy_count: 25,
      strategy_counts_by_status: { DRAFT: 25 },
      latest_completed_backtest: null,
      as_of: "2026-09-14T00:00:00Z",
    } as never);
  });

  it("pages through server results without client-side slicing", async () => {
    const first = { items: [strategy("a", "Alpha")], total: 25, limit: 20, offset: 0 };
    const second = { items: [strategy("b", "Beta")], total: 25, limit: 20, offset: 20 };
    vi.mocked(api.listStrategyPage)
      .mockResolvedValueOnce(first)
      .mockResolvedValueOnce(second)
      .mockResolvedValue(second);
    show();
    expect(await screen.findByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText(/共 25 条/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("下一页"));
    expect(await screen.findByText("Beta")).toBeInTheDocument();
    const calls = vi.mocked(api.listStrategyPage).mock.calls;
    expect(calls[calls.length - 1][0]).toMatchObject({ limit: 20, offset: 20 });
  });

  it("filters server-side by status", async () => {
    vi.mocked(api.listStrategyPage).mockResolvedValue({
      items: [strategy("c", "Gamma")],
      total: 1,
      limit: 20,
      offset: 0,
    });
    show();
    expect(await screen.findByText("Gamma")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("按状态筛选策略"), {
      target: { value: "VALIDATED" },
    });
    const calls = vi.mocked(api.listStrategyPage).mock.calls;
    await screen.findByText("Gamma");
    expect(calls[calls.length - 1][0]).toMatchObject({ status: "VALIDATED", offset: 0 });
  });

  it("clears filters from the no-match state", async () => {
    vi.mocked(api.listStrategyPage).mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    });
    show();
    await screen.findByText("下一项发现，正在等你");
    fireEvent.change(screen.getByLabelText("搜索策略"), {
      target: { value: "zzz" },
    });
    expect(await screen.findByText("没有找到匹配的策略")).toBeInTheDocument();
    fireEvent.click(screen.getByText("清空筛选"));
    await screen.findByText("下一项发现，正在等你");
    const calls = vi.mocked(api.listStrategyPage).mock.calls;
    const last = calls[calls.length - 1][0] as Record<string, unknown>;
    expect(last["offset"]).toBe(0);
    expect(last["q"]).toBeUndefined();
  });
});
