import { tr } from "@/lib/translate";

export const STRATEGY_STATUS: Record<string, string> = {
  DRAFT: tr("common.labels.strategy.draft"),
  BACKTESTED: tr("common.labels.strategy.backtested"),
  VALIDATED: tr("common.labels.strategy.validated"),
  PAPER: tr("common.labels.strategy.paper"),
  APPROVED: tr("common.labels.strategy.approved"),
  LIVE: tr("common.labels.strategy.live"),
  PAUSED: tr("common.labels.strategy.paused"),
  ARCHIVED: tr("common.labels.strategy.archived"),
};

export const BACKTEST_STATUS: Record<string, string> = {
  QUEUED: tr("common.queued"),
  STARTING: tr("common.labels.starting"),
  RUNNING: tr("common.labels.running"),
  COMPLETED: tr("common.labels.completed"),
  FAILED: tr("common.labels.failed"),
  CANCELLED: tr("common.labels.cancelled"),
};

export const BACKTEST_STEP: Record<string, string> = {
  Queued: tr("common.queued"),
  "Preparing environment": tr("common.labels.preparingEnvironment"),
  "Loading data": tr("common.labels.loadingData"),
  "Running algorithm": tr("common.labels.runningAlgorithm"),
  "Calculating metrics": tr("common.labels.calculatingMetrics"),
  "Generating validation report": tr("common.labels.generatingReport"),
  Completed: tr("common.labels.completed"),
  Failed: tr("common.labels.failed"),
  Cancelled: tr("common.labels.cancelled"),
};

export const TRADE_DIRECTION: Record<string, string> = {
  BUY: tr("common.trade.buy"),
  SELL: tr("common.trade.sell"),
  LONG: tr("common.trade.long"),
  SHORT: tr("common.trade.short"),
  HOLD: tr("common.trade.hold"),
  "1": tr("common.trade.buy"),
  "-1": tr("common.trade.sell"),
  "0": tr("common.trade.flat"),
};

export function isSellTrade(direction: string, quantity?: number): boolean {
  if (quantity != null) return quantity < 0;
  const key = String(direction).toUpperCase();
  return key === "SELL" || key === "-1";
}

export function labelDirection(direction: string, quantity?: number): string {
  if (quantity != null) {
    return quantity < 0 ? tr("common.trade.sell") : tr("common.trade.buy");
  }
  const key = String(direction).toUpperCase();
  return TRADE_DIRECTION[key] || TRADE_DIRECTION[String(direction)] || direction;
}

export const BACKTEST_TONE: Record<string, "green" | "red" | "blue" | "neutral" | "amber"> = {
  COMPLETED: "green",
  FAILED: "red",
  CANCELLED: "neutral",
  QUEUED: "blue",
  STARTING: "blue",
  RUNNING: "blue",
};

export const METRIC_LABEL: Record<string, string> = {
  total_return: tr("common.labels.metric.totalReturn"),
  cagr: tr("common.labels.metric.cagr"),
  sharpe: tr("common.labels.metric.sharpe"),
  sortino: tr("common.labels.metric.sortino"),
  max_drawdown: tr("common.labels.metric.maxDrawdown"),
  excess_return: tr("common.labels.metric.excessReturn"),
  alpha_capm: tr("common.labels.metric.alphaCapm"),
  beta: tr("common.labels.metric.beta"),
  information_ratio: tr("common.labels.metric.informationRatio"),
  calmar: tr("common.labels.metric.calmar"),
  commission: tr("common.labels.metric.commission"),
};

export function labelStatus(status: string): string {
  return STRATEGY_STATUS[status] || BACKTEST_STATUS[status] || status;
}

export function labelStep(step: string | null | undefined): string {
  if (!step) return "";
  return BACKTEST_STEP[step] || step;
}
