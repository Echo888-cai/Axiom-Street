import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HomeDashboard } from "./home-dashboard";

vi.mock("@/components/charts/equity-curve", () => ({ EquityCurve: () => <div /> }));
vi.mock("@/lib/api", async (original) => {
  const actual = await original<typeof import("@/lib/api")>();
  return { ...actual, api: { ...actual.api, getEquity: vi.fn().mockResolvedValue([]), getMetrics: vi.fn().mockResolvedValue({}) } };
});
const overview = {
  strategy_count: 137,
  strategy_counts_by_status: { DRAFT: 137 },
  latest_completed_backtest: null,
  as_of: "2026-09-13T00:00:00Z",
};
function show(error = false) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <HomeDashboard strategies={[]} backtests={[]} overview={overview} summaryError={error} />
  </QueryClientProvider>);
}
describe("overview totals", () => {
  it("does not derive research count from a partial collection", () => {
    show();
    expect(screen.getByText("137")).toBeInTheDocument();
  });
  it("does not show cached overview totals after a request failure", () => {
    show(true);
    expect(screen.queryByText("137")).not.toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(4);
  });
});
