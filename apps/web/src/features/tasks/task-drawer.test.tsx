import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TaskDrawer } from "./task-drawer";
import type { Task } from "@/lib/api/tasks";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/components/ui/toast", () => ({ toast: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...mod,
    api: {
      ...mod.api,
      listTasks: vi.fn(),
      cancelTask: vi.fn(),
    },
  };
});

import { api } from "@/lib/api";

const sample: Task[] = [
  {
    id: "bt-1", kind: "backtest", title: "E2E · 2018-01-01 → 2020-12-31",
    status: "RUNNING", progress_step: "Running algorithm",
    created_at: "2026-09-14T08:00:00Z", cancelable: true, ref: "/backtests/bt-1",
  },
  {
    id: "val-1", kind: "validation", title: "PBO 验证", status: "FAILED",
    created_at: "2026-09-14T07:00:00Z", cancelable: false, ref: "/validation",
  },
];

function renderDrawer(open = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <TaskDrawer open={open} onClose={() => undefined} />
    </QueryClientProvider>,
  );
}

describe("task drawer (P2.2)", () => {
  beforeEach(() => {
    vi.mocked(api.listTasks).mockResolvedValue(sample);
  });

  it("lists unified tasks with kind and status", async () => {
    renderDrawer();
    // 等待列表实际加载（“回测”字样同时出现在抽屉头部说明里，不能用作列表信号）
    const cancel = await screen.findByLabelText(
      "取消 E2E · 2018-01-01 → 2020-12-31",
    );
    expect(cancel).toBeEnabled();
    // 运行中的回测可取消；标题与进度可见（进度经 labelStep 本地化为中文）
    expect(
      screen.getByText("E2E · 2018-01-01 → 2020-12-31"),
    ).toBeInTheDocument();
    expect(screen.getByText(/运行策略/)).toBeInTheDocument();
    // 失败的验证只读展示，不给取消入口
    expect(screen.getByText("PBO 验证")).toBeInTheDocument();
    expect(screen.queryByLabelText(/取消 PBO/)).not.toBeInTheDocument();
  });

  it("delegates cancel and refreshes the list", async () => {
    vi.mocked(api.cancelTask).mockResolvedValue({ ...sample[0], status: "CANCELLED" });
    renderDrawer();
    await waitFor(() => screen.getByLabelText(/取消 E2E/));
    fireEvent.click(screen.getByLabelText(/取消 E2E/));
    await waitFor(() => expect(api.cancelTask).toHaveBeenCalledWith("bt-1"));
  });

  it("returns null when closed", () => {
    renderDrawer(false);
    expect(screen.queryByLabelText("任务中心")).not.toBeInTheDocument();
  });
});