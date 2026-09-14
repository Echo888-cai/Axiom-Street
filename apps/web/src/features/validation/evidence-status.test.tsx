import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EvidenceStatus } from "./evidence-status";
import type { Strategy, ValidationEvidence } from "@/lib/api";

vi.mock("@/lib/api", async (original) => {
  const actual = await original<typeof import("@/lib/api")>();
  return { ...actual, api: { ...actual.api, listStrategies: vi.fn(), getEvidence: vi.fn() } };
});

import { api } from "@/lib/api";

const strategies = [
  { id: "s1", name: "Demo", latest_version: { id: "v1" } },
] as unknown as Strategy[];

function evidence(overrides: Partial<ValidationEvidence> = {}): ValidationEvidence {
  return {
    strategy_id: "s1",
    strategy_version_id: "v1",
    backtest_id: "b1",
    passed: {
      WALK_FORWARD: true,
      DSR: true,
      PBO: true,
      SENSITIVITY: true,
      COST: true,
      BOOTSTRAP: true,
      REGIME: true,
      SPA: true,
    },
    reasons: {},
    ...overrides,
  };
}

function show() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <EvidenceStatus strategyId="s1" />
    </QueryClientProvider>,
  );
}

describe("EvidenceStatus", () => {
  it("shows per-kind evidence with reason and reference backtest", async () => {
    vi.mocked(api.listStrategies).mockResolvedValue(strategies);
    vi.mocked(api.getEvidence).mockResolvedValue(
      evidence({
        passed: {
          WALK_FORWARD: true,
          DSR: false,
          PBO: true,
          SENSITIVITY: true,
          COST: true,
          BOOTSTRAP: true,
          REGIME: true,
          SPA: true,
        },
        reasons: { DSR: "dsr_trial_set_changed" },
      }),
    );
    show();
    expect(await screen.findByText("DSR")).toBeInTheDocument();
    expect(await screen.findByText(/试验台账新增后旧结论过期/)).toBeInTheDocument();
    expect(screen.getByText(/项证据已过期或缺失/)).toBeInTheDocument();
    expect(screen.getByText("参考回测")).toBeInTheDocument();
  });

  it("shows all-valid state when every kind counts", async () => {
    vi.mocked(api.listStrategies).mockResolvedValue(strategies);
    vi.mocked(api.getEvidence).mockResolvedValue(evidence());
    show();
    expect(await screen.findByText(/八项证据均有效/)).toBeInTheDocument();
  });

  it("renders nothing without any strategy", () => {
    vi.mocked(api.listStrategies).mockResolvedValue([]);
    const { container } = render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <EvidenceStatus strategyId="" />
      </QueryClientProvider>,
    );
    expect(container.firstChild).toBeNull();
  });
});
