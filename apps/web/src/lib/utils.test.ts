import { describe, it, expect } from "vitest";
import {
  filterEquityByPeriod,
  formatDate,
  formatNumber,
  formatPct,
  formatUsd,
} from "@/lib/utils";

describe("formatPct", () => {
  it("renders positive percent with an explicit plus sign", () => {
    expect(formatPct(0.5)).toBe("+50.00%");
  });

  it("renders negative percent without a plus sign", () => {
    expect(formatPct(-0.25, 1)).toBe("-25.0%");
  });

  it("emits an honest dash for missing/NaN values", () => {
    expect(formatPct(null)).toBe("—");
    expect(formatPct(undefined)).toBe("—");
    expect(formatPct(NaN)).toBe("—");
  });
});

describe("formatNumber", () => {
  it("respects digit precision", () => {
    expect(formatNumber(3.14159, 2)).toBe("3.14");
    expect(formatNumber(7, 0)).toBe("7");
  });

  it("emits an honest dash for missing/NaN values", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(NaN)).toBe("—");
  });
});

describe("formatUsd", () => {
  it("emits an honest dash for missing/NaN values", () => {
    expect(formatUsd(null)).toBe("—");
    expect(formatUsd(NaN)).toBe("—");
  });
});

describe("formatDate", () => {
  it("truncates a timestamp to its date part", () => {
    expect(formatDate("2026-09-06T12:34:56")).toBe("2026-09-06");
  });

  it("emits an honest dash for empty input", () => {
    expect(formatDate("")).toBe("—");
    expect(formatDate(undefined)).toBe("—");
  });
});

describe("filterEquityByPeriod", () => {
  const series = [
    { time: "2026-01-01T00:00:00Z", value: 1 },
    { time: "2026-06-01T00:00:00Z", value: 2 },
  ];

  it("returns all points for ALL", () => {
    expect(filterEquityByPeriod(series, "ALL")).toHaveLength(2);
  });

  it("returns empty for an empty series", () => {
    expect(filterEquityByPeriod([], "1Y")).toEqual([]);
  });
});
