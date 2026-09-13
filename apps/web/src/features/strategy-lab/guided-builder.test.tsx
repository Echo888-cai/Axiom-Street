import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GuidedBuilder } from "./guided-builder";

describe("guided builder", () => {
  it("requires explicit replacement, then applies reviewed rules with working code", () => {
    const apply = vi.fn(); const pending = vi.fn();
    const { rerender } = render(<GuidedBuilder config={{}} code="original" onApply={apply} onPending={pending} />);
    const button = screen.getByRole("button", { name: "应用规则到代码" });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: /中期趋势/ }));
    expect(pending).toHaveBeenLastCalledWith(true);
    fireEvent.change(screen.getByLabelText(/持仓比例/), { target: { value: "50" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(button);
    expect(apply.mock.calls[0][0].code).toContain("0.5 if price > sma else 0.0");
    expect(apply.mock.calls[0][0].config.signal.lookback_period).toBe(100);
    expect(pending).toHaveBeenLastCalledWith(false);
    rerender(<GuidedBuilder config={apply.mock.calls[0][0].config} code={apply.mock.calls[0][0].code} onApply={apply} onPending={pending} />);
    expect(screen.getByRole("status")).toHaveTextContent("规则和代码已同步");
    fireEvent.change(screen.getByLabelText(/持仓比例/), { target: { value: "75" } });
    expect(pending).toHaveBeenLastCalledWith(true);
    expect(screen.getByRole("status")).not.toHaveTextContent("规则和代码已同步");
  });
});

it("loads saved configuration after initial fetch and preserves edited drafts across external changes", () => {
  const apply = vi.fn(); const pending = vi.fn();
  const { rerender } = render(<GuidedBuilder config={{}} code="original" onApply={apply} onPending={pending} />);
  const loaded = { universe: { symbols: ["QQQ"] }, signal: { lookback_period: 100 }, risk: { max_position_pct: 0.5 }, execution: { slippage_bps: 0 }, hypothesis: "Saved idea" };
  rerender(<GuidedBuilder config={loaded} code="original" onApply={apply} onPending={pending} />);
  expect(screen.getByLabelText(/交易标的/)).toHaveValue("QQQ");
  expect(screen.getByLabelText(/持仓比例/)).toHaveValue(50);
  expect(screen.getByRole("button", { name: /中期趋势/ })).toHaveAttribute("aria-pressed", "true");
  fireEvent.change(screen.getByLabelText(/持仓比例/), { target: { value: "75" } });
  rerender(<GuidedBuilder config={{ ...loaded, hypothesis: "External edit" }} code="custom edit" onApply={apply} onPending={pending} />);
  expect(screen.getByLabelText(/持仓比例/)).toHaveValue(75);
  expect(screen.getByLabelText(/研究想法/)).toHaveValue("Saved idea");
});
