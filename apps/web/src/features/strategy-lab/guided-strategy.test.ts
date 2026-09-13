import { describe, expect, it } from "vitest";
import { compileTrend, validateExperiment } from "./guided-strategy";
describe("guided strategy contract", () => {
  it("compiles reviewed rules into executable position, lookback and cost defaults", () => {
    const result = compileTrend({ symbol: "QQQ", lookback: 100, position: 50, slippage: 0, hypothesis: "trend" });
    expect(result.code).toContain('self.AddEquity("QQQ", Resolution.Daily)');
    expect(result.code).toContain("else 100");
    expect(result.code).toContain("0.5 if price > sma else 0.0");
    expect(result.code).toContain("slippage_bps = float(raw_slippage) if raw_slippage else 0");
    expect(result.config.signal.lookback_period).toBe(100);
    expect(result.config.risk.max_position_pct).toBe(0.5);
  });
  it.each([{ symbol: 'SPY\");evil()' }, { lookback: 0 }, { position: 101 }, { slippage: -1 }, { lookback: NaN }])("rejects invalid rules %o", (patch) => {
    expect(() => compileTrend({ symbol: "SPY", lookback: 200, position: 100, slippage: 5, hypothesis: "", ...patch })).toThrow();
  });
  it("blocks invalid experiment inputs", () => {
    expect(validateExperiment("2021-01-01", "2020-01-01", "100000")).toBe(false);
    expect(validateExperiment("2018-01-01", "2020-01-01", "-10")).toBe(false);
    expect(validateExperiment("2018-01-01", "2020-01-01", "100000")).toBe(true);
  });
});
