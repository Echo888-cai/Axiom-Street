import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TruthStrip } from "@/features/tearsheet/truth-strip";
import type { BacktestMetrics } from "@/lib/api";

// Product promise (VISION 信念二): Deflated Sharpe & overfitting probability
// must rank visually above the raw Sharpe. This test locks that ordering.
const FOLLOWING = Node.DOCUMENT_POSITION_FOLLOWING;

function expectBefore(a: HTMLElement, b: HTMLElement) {
  expect(a.compareDocumentPosition(b) & FOLLOWING).toBeTruthy();
}

function metrics(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    sharpe: 1.3,
    deflated_sharpe: 0.96,
    probabilistic_sharpe: 0.9,
    dsr_n_trials: 132,
    ...overrides,
  } as unknown as BacktestMetrics;
}

describe("TruthStrip ordering & honesty", () => {
  it("renders all honesty tiles", () => {
    render(<TruthStrip metrics={metrics()} pbo={0.2} />);
    expect(screen.getByText("Deflated Sharpe")).toBeInTheDocument();
    expect(screen.getByText("Probabilistic Sharpe")).toBeInTheDocument();
    expect(screen.getByText("过拟合概率 PBO")).toBeInTheDocument();
    expect(screen.getByText("试验次数")).toBeInTheDocument();
    expect(screen.getByText("原始夏普")).toBeInTheDocument();
  });

  it("ranks Deflated Sharpe before raw Sharpe (no burying the honest number)", () => {
    render(<TruthStrip metrics={metrics()} pbo={0.2} />);
    expectBefore(screen.getByText("Deflated Sharpe"), screen.getByText("原始夏普"));
  });

  it("ranks overfitting probability before raw Sharpe", () => {
    render(<TruthStrip metrics={metrics()} pbo={0.2} />);
    expectBefore(screen.getByText("过拟合概率 PBO"), screen.getByText("原始夏普"));
  });

  it("shows trial count as the multiple-testing denominator", () => {
    render(<TruthStrip metrics={metrics()} pbo={0.2} />);
    expect(screen.getByText("132")).toBeInTheDocument();
  });

  it("colors DSR positive when it clears the 95% line", () => {
    render(<TruthStrip metrics={metrics({ deflated_sharpe: 0.96 })} pbo={0.2} />);
    // formatPct(0.96) → "+96.00%"
    expect(screen.getByText("+96.00%")).toHaveClass("text-as-positive");
  });

  it("colors DSR negative when it fails the 95% line", () => {
    render(<TruthStrip metrics={metrics({ deflated_sharpe: 0.5 })} pbo={0.2} />);
    expect(screen.getByText("+50.00%")).toHaveClass("text-as-negative");
  });

  it("colors PBO positive when CSCV ≤ 0.5", () => {
    render(<TruthStrip metrics={metrics()} pbo={0.3} />);
    expect(screen.getByText("+30.00%")).toHaveClass("text-as-positive");
  });

  it("colors PBO negative (overfit risk) when CSCV > 0.5", () => {
    render(<TruthStrip metrics={metrics()} pbo={0.7} />);
    expect(screen.getByText("+70.00%")).toHaveClass("text-as-negative");
  });

  it("renders dash for a missing DSR instead of a fake number", () => {
    render(<TruthStrip metrics={metrics({ deflated_sharpe: null })} pbo={0.2} />);
    expect(screen.getByText("Deflated Sharpe")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("+96.00%")).not.toBeInTheDocument();
  });

  it("links to the validation desk only when a strategy is present", () => {
    const { rerender } = render(<TruthStrip metrics={metrics()} pbo={0.2} />);
    expect(screen.queryByText("打开验证台")).not.toBeInTheDocument();

    rerender(<TruthStrip metrics={metrics()} pbo={null} strategyId="strat-1" />);
    expect(screen.getByText("打开验证台")).toHaveAttribute("href", "/validation");
    // An empty PBO is an un-run test, never a silent zero.
    expect(screen.getByText(/PBO 空着是因为还没跑 CSCV/)).toBeInTheDocument();
  });
});
