import { describe, expect, it } from "vitest";
import {
  dailyReturnsFromEquity,
  histogram,
  inverseNormalCdf,
  normalizeSeries,
  qqNormal,
  rollingBeta,
  rollingSharpe,
} from "./tearsheet";

describe("dailyReturnsFromEquity", () => {
  it("computes simple returns from equity", () => {
    const { returns } = dailyReturnsFromEquity([100, 110, 99]);
    expect(returns).toHaveLength(2);
    expect(returns[0]).toBeCloseTo(0.1, 12);
    expect(returns[1]).toBeCloseTo(99 / 110 - 1, 12);
  });

  it("fails loud on non-positive equity", () => {
    const bad = dailyReturnsFromEquity([100, 0, 110]);
    expect(bad.returns).toEqual([]);
    expect(bad.error).toMatch(/非正值/);
  });
});

describe("normalizeSeries", () => {
  it("reindexes the first point to 100", () => {
    expect(normalizeSeries([50, 75, 100]).values).toEqual([100, 150, 200]);
  });
});

describe("rollingSharpe", () => {
  it("matches the sample Sharpe of a known window", () => {
    const returns = [0.01, -0.005, 0.012, -0.002, 0.008];
    const times = ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08"];
    const { points, error } = rollingSharpe(returns, times, 5, 252);
    expect(error).toBeUndefined();
    expect(points).toHaveLength(1);
    const mean = returns.reduce((s, r) => s + r, 0) / 5;
    const variance = returns.reduce((s, r) => s + (r - mean) ** 2, 0) / 4;
    expect(points[0].sharpe).toBeCloseTo((mean / Math.sqrt(variance)) * Math.sqrt(252), 10);
    expect(points[0].volatility).toBeCloseTo(Math.sqrt(variance) * Math.sqrt(252), 10);
    expect(points[0].time).toBe("2020-01-08");
  });

  it("refuses a short series instead of inventing a number", () => {
    const short = rollingSharpe([0.01, 0.02], ["a", "b"], 63);
    expect(short.points).toEqual([]);
    expect(short.error).toMatch(/不足 63/);
  });
});

describe("rollingBeta", () => {
  it("matches OLS beta and correlation on a known window", () => {
    const y = [0.01, 0.02, -0.01, 0.015, 0.005];
    const x = [0.01, 0.015, -0.005, 0.01, 0.0];
    const times = ["a", "b", "c", "d", "e"];
    const { points, error } = rollingBeta(y, x, times, 5);
    expect(error).toBeUndefined();
    const meanY = y.reduce((s, r) => s + r, 0) / 5;
    const meanX = x.reduce((s, r) => s + r, 0) / 5;
    let cov = 0;
    let varX = 0;
    let varY = 0;
    for (let i = 0; i < 5; i += 1) {
      cov += (x[i] - meanX) * (y[i] - meanY);
      varX += (x[i] - meanX) ** 2;
      varY += (y[i] - meanY) ** 2;
    }
    cov /= 4;
    varX /= 4;
    varY /= 4;
    expect(points[0].beta).toBeCloseTo(cov / varX, 12);
    expect(points[0].correlation).toBeCloseTo(cov / Math.sqrt(varX * varY), 12);
  });

  it("refuses a missing benchmark instead of beta=1", () => {
    const { points, error } = rollingBeta([0.01], [], ["a"], 63);
    expect(points).toEqual([]);
    expect(error).toMatch(/长度不一致/);
  });
});

describe("histogram", () => {
  it("puts equal-width observations into the expected bin", () => {
    const { bins, error } = histogram([0, 0, 1, 1, 1], 2);
    expect(error).toBeUndefined();
    expect(bins).toHaveLength(2);
    expect(bins[0].count).toBe(2);
    expect(bins[1].count).toBe(3);
  });
});

describe("inverseNormalCdf", () => {
  it("matches known normal quantiles", () => {
    expect(inverseNormalCdf(0.5)).toBeCloseTo(0, 8);
    expect(inverseNormalCdf(0.975)).toBeCloseTo(1.96, 4);
  });
});

describe("qqNormal", () => {
  it("places a median observation near zero theoretical quantile", () => {
    const sample = [-2, -1, 0, 1, 2];
    const { points } = qqNormal(sample);
    expect(points[2].sample).toBe(0);
    expect(points[2].theoretical).toBeCloseTo(0, 8);
  });
});
