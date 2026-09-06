import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ValidationRunForm } from "@/features/validation/ValidationRunForm";
import type { ValidationSpec } from "@/lib/api";

const mockSpec: ValidationSpec = {
  kind: "pbo",
  display_name: "Probability of Backtest Overfitting",
  description: "CSCV over parameter grid",
  auto_on_backtest: false,
  params_schema: {
    type: "object",
    properties: {
      parameter_key: { type: "string", default: "lookback", enum: ["lookback"] },
      values: { type: "array", items: { type: "integer" }, minItems: 2 },
      start_date: { type: "string", format: "date" },
      end_date: { type: "string", format: "date" },
    },
    required: ["values"],
  },
};

describe("ValidationRunForm", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: "test-run-id" }),
    });
  });

  it("renders spec display name and description", () => {
    render(<ValidationRunForm spec={mockSpec} strategyVersionId="ver-123" />);
    // Component uses KIND_OPTIONS label which is "PBO (过拟合概率)"
    expect(screen.getByText(/PBO.*过拟合概率/i)).toBeInTheDocument();
    expect(screen.getByText(/组合对称交叉验证.*CSCV/i)).toBeInTheDocument();
  });

  it("shows help text for the validation kind", () => {
    render(<ValidationRunForm spec={mockSpec} strategyVersionId="ver-123" />);
    expect(screen.getByText(/策略必须读取 LEAN 参数 lookback/)).toBeInTheDocument();
  });

  it("renders required array field with JSON input", () => {
    render(<ValidationRunForm spec={mockSpec} strategyVersionId="ver-123" />);
    const textarea = screen.getByPlaceholderText("JSON 数组，如 [1, 2, 3]");
    expect(textarea).toBeInTheDocument();
  });

  it("renders strategy version and backtest id as disabled inputs", () => {
    render(<ValidationRunForm spec={mockSpec} strategyVersionId="ver-123" backtestId="bt-456" />);
    expect(screen.getByDisplayValue("ver-123")).toBeDisabled();
    expect(screen.getByDisplayValue("bt-456")).toBeDisabled();
  });

  it("renders submit button", () => {
    render(<ValidationRunForm spec={mockSpec} strategyVersionId="ver-123" />);
    expect(screen.getByRole("button", { name: /发起验证/ })).toBeInTheDocument();
  });
});