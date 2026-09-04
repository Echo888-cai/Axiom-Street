import type { Metrics } from "./types";

export interface CopilotContext {
  page: string;
  symbol: string;
  strategyName: string;
  version: string;
  range: string;
  metrics?: Metrics;
}

export interface CopilotAction {
  id: string;
  label: string;
  hint?: string;
}

export interface CopilotReply {
  summary: string;
  drivers?: { n: string; title: string; detail: string }[];
  callout?: { tone: "warn" | "info"; text: string };
  actions: CopilotAction[];
}

interface Preset {
  match: RegExp;
  reply: (ctx: CopilotContext) => CopilotReply;
}

const PRESETS: Preset[] = [
  {
    match: /break|2022|drawdown|regime|underperform/i,
    reply: (ctx) => ({
      summary: `Performance regime changed significantly after March 2022. ${ctx.strategyName} went from +9.1% annualized alpha to −3.0% while turnover rose ~40%. The edge didn't vanish overnight — it decayed as the macro driver of momentum inverted.`,
      drivers: [
        { n: "01", title: "Rate regime shift", detail: "Real yields moved +380bps in 9 months. Long-duration momentum entries systematically bought the top of each compression rally." },
        { n: "02", title: "Momentum factor reversal", detail: "12-1 momentum returned −18% in 2022 vs +11% the prior three years. The strategy's lookback (45d) sat in the worst part of the term structure." },
        { n: "03", title: "Increased turnover", detail: "Whipsaw entries doubled round-trips. Cost drag rose from 1.1% to 2.6% annualized." },
        { n: "04", title: "Exposure concentration", detail: "Top-3 names carried 61% of sleeve risk into the drawdown. v18's asymmetric sizing caps this at 38%." },
      ],
      callout: { tone: "warn", text: "41 trials have run against this data snapshot. Further parameter search carries a real multiple-testing penalty — prefer structural changes over re-tuning." },
      actions: [
        { id: "analyze-regime", label: "Analyze regime", hint: "Decompose returns by macro regime" },
        { id: "compare-2021-2022", label: "Compare 2021 vs 2022", hint: "Side-by-side tearsheets" },
        { id: "run-experiment", label: "Run experiment", hint: "Queue a controlled variation" },
        { id: "adjust-params", label: "Adjust parameters", hint: "Open parameter panel" },
      ],
    }),
  },
  {
    match: /overfit|deflated|pbo|multiple.?test|real|trust/i,
    reply: (ctx) => ({
      summary: `Raw Sharpe is ${ctx.metrics ? ctx.metrics.sharpe.toFixed(2) : "1.87"}, but that number is pre-selection. With 41 logged trials on this snapshot, Deflated Sharpe is 1.12 and PBO sits at 18%. The edge survives the haircut — narrowly. The honest read: real but modest, and every additional re-tune moves it toward coincidence.`,
      drivers: [
        { n: "01", title: "Selection pressure", detail: "41 trials is the denominator. DSR discounts the observed Sharpe by the expected max under the null." },
        { n: "02", title: "Parameter plateau", detail: "Sharpe stays >1.4 across lookback 35–70. A plateau, not an isolated peak — the strongest evidence against overfitting." },
        { n: "03", title: "Cost sensitivity", detail: "Break-even cost is 4.1bps vs 1.8bps modeled. Headroom exists but is thinner than the raw curve suggests." },
      ],
      actions: [
        { id: "run-experiment", label: "Run walk-forward", hint: "12 folds, anchored" },
        { id: "open-validation", label: "Open validation desk" },
      ],
    }),
  },
  {
    match: /v18|changed|diff|version|improve/i,
    reply: () => ({
      summary: `v18 improves Sharpe primarily by reducing downside volatility, not by adding return. Sortino rose 0.31 while CAGR fell 1.2pts. The trade-off is deliberate — but note performance is now more concentrated in US Technology (61% of risk vs 44% in v16).`,
      drivers: [
        { n: "01", title: "Asymmetric sizing", detail: "Losing positions cut at 2.5% stop, winners re-entered slowly. Left tail compressed by ~30%." },
        { n: "02", title: "Faster de-risking", detail: "Crash overlay now triggers at 0.15× beta within 2 sessions vs 5 in v17." },
        { n: "03", title: "Concentration cost", detail: "Fewer qualifying names after the trend filter → sector breadth narrowed." },
      ],
      actions: [
        { id: "compare-versions", label: "Compare v14 → v18", hint: "Multi-curve overlay" },
        { id: "run-experiment", label: "Run experiment" },
      ],
    }),
  },
  {
    match: /risk|exposure|concentrat|position/i,
    reply: () => ({
      summary: `Gross exposure averages 0.83 and caps at 1.20. Current book: 61% US Technology, 22% Communication, 17% cash buffer. Largest single-name risk is NVDA at 14% of sleeve vol. No breach of limits, but factor correlation to QQQ is 0.81 — this book is one factor away from being an index with fees.`,
      actions: [
        { id: "open-portfolio", label: "Open portfolio", hint: "Positions & factor exposure" },
        { id: "analyze-regime", label: "Decompose factor risk" },
      ],
    }),
  },
];

const FALLBACK = (ctx: CopilotContext): CopilotReply => ({
  summary: `Context loaded — ${ctx.strategyName} ${ctx.version} on ${ctx.symbol}, range ${ctx.range}. I can explain the 2022 regime break, check overfitting pressure across your 41 logged trials, diff v18 against earlier versions, or decompose current risk. What do you want to pressure-test?`,
  actions: [
    { id: "q-break", label: "Why did the strategy break in 2022?" },
    { id: "q-overfit", label: "Is this strategy overfit?" },
    { id: "q-v18", label: "What changed in v18?" },
  ],
});

export function askCopilot(question: string, ctx: CopilotContext): CopilotReply {
  for (const p of PRESETS) {
    if (p.match.test(question)) return p.reply(ctx);
  }
  return FALLBACK(ctx);
}

export const SUGGESTED_PROMPTS = [
  "Why did the strategy break in 2022?",
  "Is this strategy overfit?",
  "What changed in v18?",
  "Decompose current risk",
];
