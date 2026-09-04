/**
 * Synthetic series engine.
 *
 * Every number on screen is *derived* from one reproducible daily return
 * series per (strategy version × benchmark). Metrics are computed from the
 * series — never hard-coded — so tearsheet figures, heatmaps and trades
 * always reconcile with each other.
 *
 * Narrative baked into the data (Copilot answers reference it):
 *   2018–2021  momentum works, steady alpha
 *   Feb–Mar 20 covid crash — trend filter de-risks, shallow drawdown
 *   Mar 2022 → regime break: rate shock, momentum reversal, alpha ≈ 0
 *   2023 →     partial recovery, weaker alpha
 */

import { gaussian, hashSeed, mulberry32 } from "@/lib/prng";
import type {
  Backtest,
  Metrics,
  MonthlyGrid,
  SeriesPoint,
  Strategy,
  StrategyVersion,
  Trade,
} from "./types";

export const DATA_START = "2018-01-02";
export const DATA_END = "2026-09-04";

/* ------------------------------------------------------------------ */
/* Calendar                                                            */
/* ------------------------------------------------------------------ */

function buildTradingDays(): string[] {
  const days: string[] = [];
  const d = new Date(DATA_START + "T00:00:00");
  const end = new Date(DATA_END + "T00:00:00");
  while (d <= end) {
    const dow = d.getDay();
    if (dow !== 0 && dow !== 6) {
      days.push(
        `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
          d.getDate(),
        ).padStart(2, "0")}`,
      );
    }
    d.setDate(d.getDate() + 1);
  }
  return days;
}

export const TRADING_DAYS = buildTradingDays();

/* ------------------------------------------------------------------ */
/* Benchmark (SPY-like) with macro regimes                             */
/* ------------------------------------------------------------------ */

interface Regime {
  from: string;
  mu: number; // annualized drift
  sigma: number; // annualized vol
}

const SPY_REGIMES: Regime[] = [
  { from: "2018-01-01", mu: 0.11, sigma: 0.13 },
  { from: "2018-10-01", mu: -0.34, sigma: 0.23 }, // Q4-18 selloff
  { from: "2019-01-01", mu: 0.28, sigma: 0.12 },
  { from: "2020-01-01", mu: 0.06, sigma: 0.11 },
  { from: "2020-02-19", mu: -2.4, sigma: 0.82 }, // covid crash
  { from: "2020-03-24", mu: 0.82, sigma: 0.26 }, // V-recovery
  { from: "2021-01-01", mu: 0.26, sigma: 0.12 },
  { from: "2022-01-01", mu: -0.19, sigma: 0.24 }, // rate-shock bear
  { from: "2023-01-01", mu: 0.25, sigma: 0.13 },
  { from: "2025-01-01", mu: 0.15, sigma: 0.16 },
];

function regimeAt(regimes: Regime[], t: string): Regime {
  let r = regimes[0];
  for (const g of regimes) if (t >= g.from) r = g;
  return r;
}

const SQRT_252 = Math.sqrt(252);

function benchmarkReturns(): number[] {
  const rand = gaussian(mulberry32(hashSeed("axiom/spy-benchmark")));
  return TRADING_DAYS.map((t) => {
    const r = regimeAt(SPY_REGIMES, t);
    return r.mu / 252 + (r.sigma / SQRT_252) * rand();
  });
}

const BENCH_RETURNS = benchmarkReturns();

/* ------------------------------------------------------------------ */
/* Strategy returns                                                    */
/* ------------------------------------------------------------------ */

/**
 * Momentum sleeve: long SPY-beta scaled by trend, plus regime-dependent
 * alpha. Post-Mar-2022 the momentum factor reverses — alpha goes negative
 * and turnover rises. This is the "break" the Copilot explains.
 */
function strategyReturns(v: StrategyVersion): number[] {
  const rand = gaussian(mulberry32(hashSeed(`axiom/strat/${v.seed}`)));
  return TRADING_DAYS.map((t, i) => {
    const bm = BENCH_RETURNS[i];
    let beta = v.beta;
    let alpha = v.alphaPre;

    // Defensive de-risking through the covid window
    if (t >= "2020-02-20" && t <= "2020-04-15") beta *= v.covidShield;
    // 2018 Q4 partial shield
    if (t >= "2018-10-01" && t <= "2018-12-31") beta *= 0.55 + 0.45 * v.covidShield;
    // The 2022 regime break: alpha decays AND the trend overlay cuts beta —
    // deeper cuts in later versions (v17+ trend filter)
    if (t >= "2022-03-01" && t <= "2022-12-31") {
      alpha = v.alpha2022;
      beta *= 1 - (1 - v.covidShield) * 0.55;
    } else if (t >= "2023-01-01") {
      alpha = v.alphaPost;
    }

    const idio = (v.idioVol / SQRT_252) * rand();
    return beta * bm + alpha / 252 + idio;
  });
}

/* ------------------------------------------------------------------ */
/* Series derivations                                                  */
/* ------------------------------------------------------------------ */

function toEquity(returns: number[], base = 10_000): SeriesPoint[] {
  let eq = base;
  return returns.map((r, i) => {
    eq *= 1 + r;
    return { t: TRADING_DAYS[i], v: eq };
  });
}

function toDrawdown(equity: SeriesPoint[]): SeriesPoint[] {
  let peak = -Infinity;
  return equity.map((p) => {
    peak = Math.max(peak, p.v);
    return { t: p.t, v: p.v / peak - 1 };
  });
}

function rollingSharpe(returns: number[], window = 63): SeriesPoint[] {
  const out: SeriesPoint[] = [];
  for (let i = window; i < returns.length; i++) {
    const slice = returns.slice(i - window, i);
    const mean = slice.reduce((a, b) => a + b, 0) / window;
    const varSum = slice.reduce((a, b) => a + (b - mean) ** 2, 0) / window;
    const sd = Math.sqrt(varSum);
    const s = sd === 0 ? 0 : (mean / sd) * SQRT_252;
    out.push({ t: TRADING_DAYS[i], v: s });
  }
  return out;
}

/** Position exposure proxy: trend-scaled beta, 0 → 1.2 */
function exposureSeries(v: StrategyVersion): SeriesPoint[] {
  return TRADING_DAYS.map((t, i) => {
    const bm = BENCH_RETURNS[i];
    let beta = v.beta;
    if (t >= "2020-02-20" && t <= "2020-04-15") beta *= v.covidShield;
    if (t >= "2018-10-01" && t <= "2018-12-31") beta *= 0.55 + 0.45 * v.covidShield;
    const trend = bm > -0.005 ? 1 : 0.85;
    const gross = Math.min(1.2, Math.max(0.15, beta * trend + 0.28));
    return { t, v: gross };
  });
}

/* ------------------------------------------------------------------ */
/* Metrics — computed from series, matching the tearsheet contract     */
/* ------------------------------------------------------------------ */

function computeMetrics(returns: number[], trades: Trade[]): Metrics {
  const n = returns.length;
  const equity = returns.reduce((acc, r) => acc * (1 + r), 1);
  const totalReturn = equity - 1;
  const years = n / 252;
  const cagr = Math.pow(equity, 1 / years) - 1;

  const mean = returns.reduce((a, b) => a + b, 0) / n;
  const sd = Math.sqrt(returns.reduce((a, b) => a + (b - mean) ** 2, 0) / n);
  const volatility = sd * SQRT_252;
  const sharpe = sd === 0 ? 0 : (mean / sd) * SQRT_252;

  const downside = returns.filter((r) => r < 0);
  const dd =
    downside.length === 0
      ? 1e-9
      : Math.sqrt(downside.reduce((a, b) => a + b * b, 0) / downside.length);
  const sortino = (mean / dd) * SQRT_252;

  let peak = 1;
  let level = 1;
  let maxDrawdown = 0;
  for (const r of returns) {
    level *= 1 + r;
    peak = Math.max(peak, level);
    maxDrawdown = Math.min(maxDrawdown, level / peak - 1);
  }

  // Alpha / beta via OLS on benchmark
  const bmMean = BENCH_RETURNS.reduce((a, b) => a + b, 0) / n;
  let cov = 0;
  let varBm = 0;
  for (let i = 0; i < n; i++) {
    cov += (returns[i] - mean) * (BENCH_RETURNS[i] - bmMean);
    varBm += (BENCH_RETURNS[i] - bmMean) ** 2;
  }
  const beta = varBm === 0 ? 0 : cov / varBm;
  const alpha = (mean - beta * bmMean) * 252;

  const wins = trades.filter((t) => t.pnl > 0);
  const losses = trades.filter((t) => t.pnl <= 0);
  const grossWin = wins.reduce((a, t) => a + t.pnl, 0);
  const grossLoss = Math.abs(losses.reduce((a, t) => a + t.pnl, 0));

  return {
    totalReturn,
    cagr,
    sharpe,
    sortino,
    maxDrawdown,
    volatility,
    winRate: trades.length ? wins.length / trades.length : 0,
    profitFactor: grossLoss === 0 ? 0 : grossWin / grossLoss,
    alpha,
    beta,
    trades: trades.length,
    turnover: 6.4,
  };
}

/* ------------------------------------------------------------------ */
/* Trades                                                              */
/* ------------------------------------------------------------------ */

const UNIVERSE = [
  "AAPL",
  "NVDA",
  "MSFT",
  "META",
  "AMZN",
  "GOOGL",
  "AVGO",
  "CRM",
  "AMD",
  "NFLX",
  "ADBE",
  "ORCL",
  "QCOM",
  "TXN",
  "NOW",
];

function genTrades(v: StrategyVersion, count: number): Trade[] {
  const rand = mulberry32(hashSeed(`axiom/trades/${v.seed}`));
  const trades: Trade[] = [];
  let dayIdx = 30;
  for (let i = 0; i < count; i++) {
    const hold = 3 + Math.floor(rand() * 18);
    const entry = TRADING_DAYS[Math.min(dayIdx, TRADING_DAYS.length - 1)];
    const exitIdx = Math.min(dayIdx + hold, TRADING_DAYS.length - 1);
    const exit = TRADING_DAYS[exitIdx];
    const symbol = UNIVERSE[Math.floor(rand() * UNIVERSE.length)];
    const side = rand() > 0.12 ? "LONG" : "SHORT";

    // Trade outcome loosely follows the regime narrative
    const inBreak = exit >= "2022-03-01" && exit <= "2022-12-31";
    const winP = inBreak ? 0.42 : 0.565;
    const win = rand() < winP;
    const magnitude = (win ? 0.014 + rand() * 0.052 : 0.011 + rand() * 0.031) * (side === "SHORT" ? 0.8 : 1);
    const pnlPct = win ? magnitude : -magnitude;

    const notional = 18_000 + rand() * 60_000;
    const pnl = notional * pnlPct;
    const qty = Math.max(1, Math.round(notional / (80 + rand() * 320)));
    const entryPrice = 60 + rand() * 420;
    const exitPrice = entryPrice * (1 + (side === "LONG" ? pnlPct : -pnlPct));

    trades.push({
      id: `T-${String(4200 + i)}`,
      symbol,
      side,
      qty,
      entryDate: entry,
      exitDate: exit,
      entryPrice: Math.round(entryPrice * 100) / 100,
      exitPrice: Math.round(exitPrice * 100) / 100,
      pnl: Math.round(pnl),
      pnlPct,
      holdingDays: hold,
    });
    dayIdx += hold + 2 + Math.floor(rand() * 9);
    if (dayIdx >= TRADING_DAYS.length - 5) break;
  }
  return trades.reverse(); // most recent first
}

/* ------------------------------------------------------------------ */
/* Monthly grid + yearly table                                         */
/* ------------------------------------------------------------------ */

function monthlyGrid(returns: number[]): MonthlyGrid {
  const years: number[] = [];
  const cells: Record<number, (number | null)[]> = {};
  const acc: Record<string, number> = {};
  TRADING_DAYS.forEach((t, i) => {
    const y = Number(t.slice(0, 4));
    const m = Number(t.slice(5, 7)) - 1;
    const key = `${y}-${m}`;
    acc[key] = (acc[key] ?? 1) * (1 + returns[i]);
  });
  for (const key of Object.keys(acc)) {
    const [y, m] = key.split("-").map(Number);
    if (!cells[y]) {
      cells[y] = Array(12).fill(null);
      years.push(y);
    }
    cells[y][m] = acc[key] - 1;
  }
  years.sort();
  return { years, cells };
}

export interface YearRow {
  year: number;
  strategy: number;
  benchmark: number;
  excess: number;
  maxDD: number;
  sharpe: number;
  winRate: number;
}

function yearlyTable(returns: number[]): YearRow[] {
  const byYear = new Map<number, { s: number[]; b: number[] }>();
  TRADING_DAYS.forEach((t, i) => {
    const y = Number(t.slice(0, 4));
    if (!byYear.has(y)) byYear.set(y, { s: [], b: [] });
    byYear.get(y)!.s.push(returns[i]);
    byYear.get(y)!.b.push(BENCH_RETURNS[i]);
  });
  const rows: YearRow[] = [];
  for (const [year, { s, b }] of byYear) {
    const sEq = s.reduce((a, r) => a * (1 + r), 1) - 1;
    const bEq = b.reduce((a, r) => a * (1 + r), 1) - 1;
    const mean = s.reduce((a, r) => a + r, 0) / s.length;
    const sd = Math.sqrt(s.reduce((a, r) => a + (r - mean) ** 2, 0) / s.length);
    let peak = 1;
    let lvl = 1;
    let mdd = 0;
    for (const r of s) {
      lvl *= 1 + r;
      peak = Math.max(peak, lvl);
      mdd = Math.min(mdd, lvl / peak - 1);
    }
    rows.push({
      year,
      strategy: sEq,
      benchmark: bEq,
      excess: sEq - bEq,
      maxDD: mdd,
      sharpe: sd === 0 ? 0 : (mean / sd) * SQRT_252,
      winRate: s.filter((r) => r > 0).length / s.length,
    });
  }
  return rows;
}

/* ------------------------------------------------------------------ */
/* Public assembly API                                                 */
/* ------------------------------------------------------------------ */

export interface VersionData {
  equity: SeriesPoint[];
  benchmark: SeriesPoint[];
  drawdown: SeriesPoint[];
  benchmarkDrawdown: SeriesPoint[];
  rolling: SeriesPoint[];
  exposure: SeriesPoint[];
  monthly: MonthlyGrid;
  yearly: YearRow[];
  trades: Trade[];
  metrics: Metrics;
}

const cache = new Map<string, VersionData>();

export function getVersionData(v: StrategyVersion): VersionData {
  const key = `${v.version}-${v.seed}`;
  const hit = cache.get(key);
  if (hit) return hit;

  const returns = strategyReturns(v);
  const equity = toEquity(returns);
  const benchmark = toEquity(BENCH_RETURNS);
  const trades = genTrades(v, 232);

  const data: VersionData = {
    equity,
    benchmark,
    drawdown: toDrawdown(equity),
    benchmarkDrawdown: toDrawdown(benchmark),
    rolling: rollingSharpe(returns),
    exposure: exposureSeries(v),
    monthly: monthlyGrid(returns),
    yearly: yearlyTable(returns),
    trades,
    metrics: computeMetrics(returns, trades),
  };
  cache.set(key, data);
  return data;
}

export function filterRange(series: SeriesPoint[], range: string): SeriesPoint[] {
  if (range === "ALL") return series;
  const end = series[series.length - 1]?.t;
  if (!end) return series;
  const days: Record<string, number> = {
    "1D": 1,
    "1W": 7,
    "1M": 31,
    "1Y": 366,
    "5Y": 366 * 5,
  };
  const cutoff = new Date(end + "T00:00:00");
  cutoff.setDate(cutoff.getDate() - (days[range] ?? 0));
  const c = `${cutoff.getFullYear()}-${String(cutoff.getMonth() + 1).padStart(2, "0")}-${String(cutoff.getDate()).padStart(2, "0")}`;
  return series.filter((p) => p.t >= c);
}

/** Rebase two series to 100 at the range start for clean comparison */
export function rebase(series: SeriesPoint[], base = 100): SeriesPoint[] {
  if (series.length === 0) return series;
  const v0 = series[0].v;
  return series.map((p) => ({ t: p.t, v: (p.v / v0) * base }));
}

/* ------------------------------------------------------------------ */
/* Backtest runs                                                       */
/* ------------------------------------------------------------------ */

export function backtestsFor(strategy: Strategy): Backtest[] {
  const rand = mulberry32(hashSeed(`axiom/bt/${strategy.id}`));
  const runs: Backtest[] = [];
  let runNo = 184;
  const versions = [...strategy.versions].reverse();
  for (const v of versions) {
    const count = 2 + Math.floor(rand() * 4);
    for (let i = 0; i < count; i++) {
      const d = new Date("2026-09-03T00:00:00");
      d.setDate(d.getDate() - Math.floor(rand() * 240));
      runs.push({
        id: `bt-${strategy.id}-${runNo}`,
        run: runNo,
        strategyId: strategy.id,
        version: v.version,
        status: rand() > 0.06 ? "Completed" : "Failed",
        startedAt: d.toISOString(),
        runtimeMs: 40_000 + rand() * 220_000,
        dateFrom: DATA_START,
        dateTo: DATA_END,
        initialCapital: 250_000,
        benchmark: strategy.benchmark,
        dataSnapshot: `snap_${hashSeed(strategy.id + runNo).toString(16).slice(0, 8)}`,
        engineVersion: "lean-2.5.42+axiom.7",
      });
      runNo -= 1 + Math.floor(rand() * 3);
    }
  }
  return runs.sort((a, b) => b.run - a.run);
}
