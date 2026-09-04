export type TimeRange = "1D" | "1W" | "1M" | "1Y" | "5Y" | "ALL";

export interface SeriesPoint {
  /** yyyy-mm-dd */
  t: string;
  v: number;
}

export interface Candle {
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
  vol: number;
}

export type StrategyStatus = "LIVE" | "PAPER" | "DRAFT";

export interface StrategyParams {
  lookback: number;
  threshold: number;
  stopLoss: number;
  rebalance: "Daily" | "Weekly" | "Monthly";
  volTarget: number;
}

export interface StrategyVersion {
  version: string;
  createdAt: string;
  note: string;
  params: StrategyParams;
  seed: number;
  beta: number;
  covidShield: number;
  alphaPre: number;
  alpha2022: number;
  alphaPost: number;
  idioVol: number;
}

export interface Strategy {
  id: string;
  name: string;
  status: StrategyStatus;
  createdAt: string;
  lastRun: string;
  universe: string;
  benchmark: string;
  timeframe: string;
  description: string;
  currentVersion: string;
  versions: StrategyVersion[];
}

export interface Metrics {
  totalReturn: number;
  cagr: number;
  sharpe: number;
  sortino: number;
  maxDrawdown: number;
  volatility: number;
  winRate: number;
  profitFactor: number;
  alpha: number;
  beta: number;
  trades: number;
  turnover: number;
}

export type BacktestStatus = "Completed" | "Running" | "Failed" | "Queued";

export interface Backtest {
  id: string;
  run: number;
  strategyId: string;
  version: string;
  status: BacktestStatus;
  startedAt: string;
  runtimeMs: number;
  dateFrom: string;
  dateTo: string;
  initialCapital: number;
  benchmark: string;
  dataSnapshot: string;
  engineVersion: string;
}

export interface Trade {
  id: string;
  symbol: string;
  side: "LONG" | "SHORT";
  qty: number;
  entryDate: string;
  exitDate: string;
  entryPrice: number;
  exitPrice: number;
  pnl: number;
  pnlPct: number;
  holdingDays: number;
}

export interface SymbolInfo {
  symbol: string;
  name: string;
  sector: string;
  price: number;
  changePct: number;
  marketCap: number;
  pe: number;
  eps: number;
  revenue: number;
  fcf: number;
  roe: number;
}

export interface MonthlyGrid {
  years: number[];
  /** [year][month 0-11] → return | null */
  cells: Record<number, (number | null)[]>;
}
