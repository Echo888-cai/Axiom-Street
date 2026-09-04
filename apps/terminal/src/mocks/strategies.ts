import type { Strategy } from "./types";

/**
 * Strategy catalog. Version history tells a real research story:
 * each version exists because the previous one failed in a specific way.
 */
export const STRATEGIES: Strategy[] = [
  {
    id: "strat-momentum-alpha",
    name: "Momentum Alpha",
    status: "LIVE",
    createdAt: "2024-11-08",
    lastRun: "2026-09-03T14:22:00",
    universe: "US Large-Cap Tech · 15 names",
    benchmark: "SPY",
    timeframe: "Daily",
    description:
      "Cross-sectional momentum over US large-cap technology with trend-filtered beta, volatility targeting at 12% and a defensive de-risking overlay.",
    currentVersion: "v18",
    versions: [
      {
        version: "v14",
        createdAt: "2024-11-08",
        note: "Baseline cross-sectional momentum, constant beta.",
        params: { lookback: 60, threshold: 0.2, stopLoss: 0.05, rebalance: "Weekly", volTarget: 0.18 },
        seed: 1401,
        beta: 0.78,
        covidShield: 1.0,
        alphaPre: 0.06,
        alpha2022: -0.075,
        alphaPost: 0.02,
        idioVol: 0.09,
      },
      {
        version: "v15",
        createdAt: "2025-02-14",
        note: "Add crash overlay — cut beta when trend inverts.",
        params: { lookback: 60, threshold: 0.2, stopLoss: 0.04, rebalance: "Weekly", volTarget: 0.15 },
        seed: 1502,
        beta: 0.7,
        covidShield: 0.35,
        alphaPre: 0.065,
        alpha2022: -0.06,
        alphaPost: 0.028,
        idioVol: 0.085,
      },
      {
        version: "v16",
        createdAt: "2025-06-21",
        note: "Volatility targeting 12%; position sizes scale inversely with realized vol.",
        params: { lookback: 45, threshold: 0.25, stopLoss: 0.04, rebalance: "Weekly", volTarget: 0.12 },
        seed: 1603,
        beta: 0.62,
        covidShield: 0.3,
        alphaPre: 0.07,
        alpha2022: -0.05,
        alphaPost: 0.035,
        idioVol: 0.075,
      },
      {
        version: "v17",
        createdAt: "2025-12-02",
        note: "Trend filter on the universe; skip names below their 100D mean.",
        params: { lookback: 45, threshold: 0.3, stopLoss: 0.03, rebalance: "Weekly", volTarget: 0.12 },
        seed: 1704,
        beta: 0.58,
        covidShield: 0.25,
        alphaPre: 0.078,
        alpha2022: -0.042,
        alphaPost: 0.045,
        idioVol: 0.068,
      },
      {
        version: "v18",
        createdAt: "2026-05-19",
        note: "Downside-vol reduction: asymmetric sizing, faster stop, slower re-entry.",
        params: { lookback: 45, threshold: 0.3, stopLoss: 0.025, rebalance: "Weekly", volTarget: 0.12 },
        seed: 1805,
        beta: 0.55,
        covidShield: 0.15,
        alphaPre: 0.088,
        alpha2022: -0.022,
        alphaPost: 0.062,
        idioVol: 0.048,
      },
    ],
  },
  {
    id: "strat-mean-reversion-spx",
    name: "SPX Mean Reversion",
    status: "PAPER",
    createdAt: "2025-04-02",
    lastRun: "2026-08-28T09:41:00",
    universe: "SPY + ES hedge",
    benchmark: "SPY",
    timeframe: "Hourly",
    description:
      "Short-horizon reversal on index futures, z-score entries, strict session close-out.",
    currentVersion: "v6",
    versions: [
      {
        version: "v6",
        createdAt: "2026-03-11",
        note: "Session close-out; remove overnight carry.",
        params: { lookback: 20, threshold: 0.5, stopLoss: 0.02, rebalance: "Daily", volTarget: 0.08 },
        seed: 6201,
        beta: 0.22,
        covidShield: 0.5,
        alphaPre: 0.05,
        alpha2022: 0.02,
        alphaPost: 0.04,
        idioVol: 0.05,
      },
    ],
  },
  {
    id: "strat-vol-carry",
    name: "Volatility Carry",
    status: "DRAFT",
    createdAt: "2026-01-15",
    lastRun: "2026-08-19T17:03:00",
    universe: "VIX front two months",
    benchmark: "SPY",
    timeframe: "Daily",
    description: "Short-dated variance carry with tail hedge budget capped at 40bps/month.",
    currentVersion: "v2",
    versions: [
      {
        version: "v2",
        createdAt: "2026-06-30",
        note: "Tail hedge budget cap.",
        params: { lookback: 30, threshold: 0.15, stopLoss: 0.08, rebalance: "Daily", volTarget: 0.1 },
        seed: 2202,
        beta: -0.12,
        covidShield: 0.2,
        alphaPre: 0.04,
        alpha2022: 0.06,
        alphaPost: 0.045,
        idioVol: 0.11,
      },
    ],
  },
  {
    id: "strat-cross-asset-trend",
    name: "Cross-Asset Trend",
    status: "PAPER",
    createdAt: "2025-09-27",
    lastRun: "2026-09-01T11:15:00",
    universe: "Equity index, rates, FX, metals · 22 markets",
    benchmark: "SPY",
    timeframe: "Daily",
    description: "Medium-term time-series momentum across liquid futures, equal risk contribution.",
    currentVersion: "v9",
    versions: [
      {
        version: "v9",
        createdAt: "2026-07-22",
        note: "Equal risk contribution weighting.",
        params: { lookback: 90, threshold: 0.1, stopLoss: 0.06, rebalance: "Monthly", volTarget: 0.1 },
        seed: 9203,
        beta: 0.18,
        covidShield: 0.4,
        alphaPre: 0.045,
        alpha2022: 0.09,
        alphaPost: 0.05,
        idioVol: 0.07,
      },
    ],
  },
];

export function getStrategy(id: string): Strategy {
  return STRATEGIES.find((s) => s.id === id) ?? STRATEGIES[0];
}

export function getVersion(strategy: Strategy, version?: string) {
  return (
    strategy.versions.find((v) => v.version === version) ??
    strategy.versions.find((v) => v.version === strategy.currentVersion) ??
    strategy.versions[0]
  );
}
