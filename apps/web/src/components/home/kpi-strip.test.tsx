import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KpiStrip } from "./kpi-strip";

describe("research metrics availability", () => {
  it("does not present cached figures as current when data is unavailable", () => {
    render(
      <KpiStrip
        totalReturn={0.12}
        sharpe={1.4}
        maxDrawdown={-0.08}
        strategyCount={5}
        hasBacktest
        unavailable
      />,
    );
    expect(screen.getAllByText("—")).toHaveLength(4);
    expect(screen.queryByText("1.40")).not.toBeInTheDocument();
  });
});
