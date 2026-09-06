import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MetricTile, metricTone } from "@/components/ui/metric-tile";

describe("MetricTile", () => {
  it("renders label and value", () => {
    render(<MetricTile label="Total Return" value="12.34%" />);
    expect(screen.getByText("Total Return")).toBeInTheDocument();
    expect(screen.getByText("12.34%")).toBeInTheDocument();
  });

  it("renders positive tone with positive color", () => {
    render(<MetricTile label="Sharpe" value="1.50" tone="pos" />);
    const value = screen.getByText("1.50");
    expect(value).toHaveClass("text-as-positive");
  });

  it("renders negative tone with negative color", () => {
    render(<MetricTile label="MaxDD" value="-25.00%" tone="neg" />);
    const value = screen.getByText("-25.00%");
    expect(value).toHaveClass("text-as-negative");
  });

  it("renders neutral tone with default color", () => {
    render(<MetricTile label="PnL" value="0.00" tone="neutral" />);
    const value = screen.getByText("0.00");
    expect(value).toHaveClass("text-as-text");
  });

  it("uses tabular class for financial figures", () => {
    render(<MetricTile label="Test" value="123.45" />);
    const value = screen.getByText("123.45");
    expect(value).toHaveClass("tabular");
  });

  it("shows hint when provided", () => {
    render(<MetricTile label="With Hint" value="1.0" hint="This is help text" />);
    expect(screen.getByText("This is help text")).toBeInTheDocument();
  });

  it("metricTone helper returns pos for positive", () => {
    expect(metricTone(1.5)).toBe("pos");
    expect(metricTone(0.001)).toBe("pos");
  });

  it("metricTone helper returns neg for negative", () => {
    expect(metricTone(-1.5)).toBe("neg");
    expect(metricTone(-0.001)).toBe("neg");
  });

  it("metricTone helper returns undefined for zero/null/NaN", () => {
    expect(metricTone(0)).toBeUndefined();
    expect(metricTone(null)).toBeUndefined();
    expect(metricTone(NaN)).toBeUndefined();
  });
});