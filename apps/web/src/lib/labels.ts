export const STRATEGY_STATUS: Record<string, string> = {
  DRAFT: "草稿",
  BACKTESTED: "已回测",
  VALIDATED: "已验证",
  PAPER: "模拟",
  APPROVED: "已批准",
  LIVE: "实盘",
  PAUSED: "暂停",
  ARCHIVED: "归档",
};

export const BACKTEST_STATUS: Record<string, string> = {
  QUEUED: "排队中",
  STARTING: "启动中",
  RUNNING: "运行中",
  COMPLETED: "已完成",
  FAILED: "失败",
  CANCELLED: "已取消",
};

export const BACKTEST_STEP: Record<string, string> = {
  Queued: "排队中",
  "Preparing environment": "准备环境",
  "Loading data": "加载数据",
  "Running algorithm": "运行策略",
  "Calculating metrics": "计算指标",
  "Generating validation report": "生成报告",
  Completed: "已完成",
  Failed: "失败",
  Cancelled: "已取消",
};

export const TRADE_DIRECTION: Record<string, string> = {
  BUY: "买入",
  SELL: "卖出",
  LONG: "做多",
  SHORT: "做空",
  HOLD: "持有",
  "1": "买入",
  "-1": "卖出",
  "0": "平仓",
};

export function labelDirection(direction: string, quantity?: number): string {
  if (quantity != null && quantity < 0) return "卖出";
  if (quantity != null && quantity > 0) return "买入";
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
  total_return: "总收益",
  cagr: "年化 CAGR",
  sharpe: "夏普",
  sortino: "索提诺",
  max_drawdown: "最大回撤",
  excess_return: "超额收益",
  alpha_capm: "CAPM α",
  beta: "β",
  information_ratio: "信息比率",
  calmar: "卡尔玛",
  commission: "佣金",
};

export function labelStatus(status: string): string {
  return STRATEGY_STATUS[status] || BACKTEST_STATUS[status] || status;
}

export function labelStep(step: string | null | undefined): string {
  if (!step) return "";
  return BACKTEST_STEP[step] || step;
}
