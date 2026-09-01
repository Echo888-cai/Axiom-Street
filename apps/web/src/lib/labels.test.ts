import { describe, expect, it } from "vitest";
import { formatPct, formatUsd } from "./utils";
import { labelStatus, METRIC_LABEL } from "./labels";

describe("labels", () => {
  it("maps excess_return to 超额收益", () => {
    expect(METRIC_LABEL.excess_return).toBe("超额收益");
  });

  it("labels strategy and backtest status", () => {
    expect(labelStatus("DRAFT")).toBe("草稿");
    expect(labelStatus("COMPLETED")).toBe("已完成");
  });
});

describe("formatters", () => {
  it("formats percent with sign", () => {
    expect(formatPct(0.1234)).toBe("+12.34%");
    expect(formatPct(null)).toBe("—");
  });

  it("formats usd", () => {
    expect(formatUsd(43, 2)).toContain("43");
    expect(formatUsd(null)).toBe("—");
  });
});
