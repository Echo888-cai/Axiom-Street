import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OperationsHealthCard } from "./operations-health-card";
import type { HealthStatus } from "@/lib/api/types";

const mocks = vi.hoisted(() => ({ health: vi.fn() }));

vi.mock("@/lib/api", () => ({ api: mocks }));

const healthy: HealthStatus = {
  status: "ok",
  service: "api",
  version: "0.1.0",
  checks: {
    postgres: { ok: true },
    redis: { ok: true },
    docker: { ok: true, image: "quantconnect/lean:16355" },
    worker: { ok: true, age_seconds: 12, image: "quantconnect/lean:16355" },
    security: { ok: true, network: "none", rootfs_read_only: true, non_root: true, seccomp: "default" },
  },
};

function renderCard() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <OperationsHealthCard />
    </QueryClientProvider>,
  );
}

describe("OperationsHealthCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.health.mockResolvedValue(healthy);
  });

  it("renders real dependency, worker, and sandbox status", async () => {
    renderCard();

    expect(await screen.findByText("运行监控")).toBeInTheDocument();
    expect(screen.getByText("运行正常")).toBeInTheDocument();
    expect(screen.getByText("12 秒前心跳")).toBeInTheDocument();
    expect(screen.getByText("只读根文件系统 · 非 root · seccomp default")).toBeInTheDocument();
  });

  it("shows degraded state and server note", async () => {
    mocks.health.mockResolvedValue({
      ...healthy,
      status: "degraded",
      checks: { ...healthy.checks, worker: { ok: false, note: "Worker 心跳已过期。" } },
    });
    renderCard();

    expect(await screen.findByText("运行降级")).toBeInTheDocument();
    expect(screen.getByText("Worker 心跳已过期。")).toBeInTheDocument();
  });

  it("shows an actionable error when health cannot be read", async () => {
    mocks.health.mockRejectedValue(new Error("连接失败"));
    renderCard();

    expect(await screen.findByText("运行监控暂不可用")).toBeInTheDocument();
    expect(screen.getByText("连接失败")).toBeInTheDocument();
  });
});
