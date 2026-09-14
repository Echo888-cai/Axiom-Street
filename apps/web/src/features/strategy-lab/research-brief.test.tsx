import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ResearchBrief } from "./research-brief";

const overview = {
  strategy_count: 137,
  strategy_counts_by_status: { DRAFT: 100, BACKTESTED: 30, VALIDATED: 7 },
  latest_completed_backtest: null,
  as_of: "2026-09-13T00:00:00Z",
};

describe("workspace research summary", () => {
  it("uses database totals rather than the loaded page", () => {
    render(<ResearchBrief overview={overview} unavailable={false} />);
    expect(screen.getByText("137")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByText("07")).toBeInTheDocument();
  });
  it("hides cached counts when the summary is unavailable", () => {
    render(<ResearchBrief overview={overview} unavailable />);
    expect(within(screen.getByRole("region", { name: "研究路径与概况" })).getAllByText("—")).toHaveLength(4);
    expect(screen.queryByText("137")).not.toBeInTheDocument();
  });
});
