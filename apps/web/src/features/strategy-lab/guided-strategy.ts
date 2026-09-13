import { SPY_200DMA_TEMPLATE } from "@/lib/spy-200dma";

export type TrendRules = { symbol: string; lookback: number; position: number; slippage: number; hypothesis: string };

export function compileTrend(rules: TrendRules) {
  const { symbol, lookback, position, slippage, hypothesis } = rules;
  if (!/^[A-Z][A-Z0-9.-]{0,9}$/.test(symbol) || !Number.isInteger(lookback) || lookback < 20 || lookback > 500 || !Number.isFinite(position) || position < 1 || position > 100 || !Number.isFinite(slippage) || slippage < 0 || slippage > 100) {
    throw new Error("请检查标的代码、均线周期（20–500）、仓位（1–100%）和滑点（0–100 bps）。");
  }
  const code = SPY_200DMA_TEMPLATE
    .replace('self.AddEquity("SPY",', `self.AddEquity("${symbol}",`)
    .replace('self.SetBenchmark("SPY")', `self.SetBenchmark("${symbol}")`)
    .replace('if raw_lookback else 200', `if raw_lookback else ${lookback}`)
    .replace('if raw_slippage else 5.0', `if raw_slippage else ${slippage}`)
    .replace('1.0 if price > sma else 0.0', `${position / 100} if price > sma else 0.0`)
    .replace(/    """SPY 200DMA[\s\S]*?    """/, '    """Rule-builder trend strategy. Close signal, next daily bar execution."""');
  return { code, config: {
    class_name: "Spy200DmaAlgorithm", hypothesis,
    universe: { asset_class: "equity", market: "US", symbols: [symbol] },
    signal: { entry_signal: `close > SMA(${lookback})`, exit_signal: `close <= SMA(${lookback})`, lookback_period: lookback, rebalance_frequency: "daily" },
    position_sizing: { model: "fixed", target_weight: position / 100 },
    risk: { max_position_pct: position / 100, stop_loss: null, portfolio_drawdown_halt: null },
    execution: { rebalance: "next_bar", slippage_bps: slippage, commission: "constant_1_usd" },
  } };
}

export function validateExperiment(start: string, end: string, capital: string) {
  const validDate = (date: string) => /^\d{4}-\d{2}-\d{2}$/.test(date) && Number.isFinite(Date.parse(date)) && new Date(date).toISOString().slice(0, 10) === date;
  return validDate(start) && validDate(end) && start < end && Number.isFinite(Number(capital)) && Number(capital) >= 1000;
}
