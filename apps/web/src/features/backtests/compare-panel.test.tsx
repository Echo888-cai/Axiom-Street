import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ComparePanel } from "@/features/backtests/compare-panel";
import type { Backtest, CompareEquityResponse } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...mod,
    api: {
      listBacktests: vi.fn(),
      compareEquity: vi.fn(),
    },
  };
});

// Canvas rendering is verified in the browser; this suite tests the table and selection.
vi.mock("@/components/charts/equity-curve", () => ({ EquityCurve: () => null }));

// api is a plain object of functions; the mock above replaces its
// implementation wholesale, so typing through the real module works.
import { api } from "@/lib/api";

const btA = {
  id: "bt-a",
  strategy_name: "Alpha",
  version_number: 1,
  start_date: "2020-01-01T00:00:00Z",
  status: "COMPLETED",
} as unknown as Backtest;

const btB = {
  id: "bt-b",
  strategy_name: "Beta",
  version_number: 2,
  start_date: "2020-01-01T00:00:00Z",
  status: "COMPLETED",
} as unknown as Backtest;

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

async function selectSecondBacktest() {
  const beta = await screen.findByRole("button", { name: /Beta/ });
  await userEvent.click(beta);
}

describe("ComparePanel", () => {
  beforeEach(() => {
    vi.mocked(api.listBacktests).mockResolvedValue([btA, btB] as Backtest[]);
    vi.mocked(api.compareEquity).mockReset().mockResolvedValue({ series: [] });
  });

  it("renders the metrics table from backend series values (RC-W4)", async () => {
    const series: CompareEquityResponse = {
      series: [
        {
          id: "bt-a",
          label: "Alpha v1",
          data: [
            { time: "2020-01-02", value: 100000 },
            { time: "2020-01-03", value: 101000 },
          ],
          metrics: {
            final_equity: 103000,
            total_return: 0.03,
            cagr: 0.021,
            sharpe: 1.05,
            max_drawdown: -0.221,
            volatility: 0.15,
            trade_count: 45,
          },
        },
        {
          id: "bt-b",
          label: "Beta v2",
          data: [
            { time: "2020-01-02", value: 100000 },
            { time: "2020-01-03", value: 99000 },
          ],
          metrics: null,
        },
      ],
    };
    vi.mocked(api.compareEquity).mockResolvedValue(series);

    render(
      <QueryClientProvider client={makeQueryClient()}>
        <ComparePanel currentBacktestId="bt-a" />
      </QueryClientProvider>,
    );

    await selectSecondBacktest();

    const rows = await screen.findAllByRole("row");
    const alphaRow = rows.find((r) => within(r).queryByText("Alpha v1"));
    expect(alphaRow).toBeTruthy();
    expect(within(alphaRow!).getByText("$103,000")).toBeInTheDocument();
    expect(within(alphaRow!).getByText("+3.00%")).toBeInTheDocument();
    expect(within(alphaRow!).getByText("+2.10%")).toBeInTheDocument();
    expect(within(alphaRow!).getByText("1.05")).toBeInTheDocument();
    expect(within(alphaRow!).getByText("-22.10%")).toBeInTheDocument();
    expect(within(alphaRow!).getByText("+15.00%")).toBeInTheDocument();
    expect(within(alphaRow!).getByText("45")).toBeInTheDocument();

    const betaRow = rows.find((r) => within(r).queryByText("Beta v2"));
    expect(betaRow).toBeTruthy();
    // No metrics attached: every numeric cell falls back to the dash.
    expect(within(betaRow!).getAllByText("—").length).toBeGreaterThanOrEqual(7);
  });

  it("keeps the metrics query disabled until two backtests are selected", async () => {
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <ComparePanel currentBacktestId="bt-a" />
      </QueryClientProvider>,
    );

    await screen.findByRole("button", { name: /Alpha/ });
    expect(api.compareEquity).not.toHaveBeenCalled();

    await selectSecondBacktest();
    await vi.waitFor(() => expect(api.compareEquity).toHaveBeenCalledTimes(1));
  });
});
