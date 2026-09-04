import { cn } from "@/lib/cn";
import type { BacktestStatus, StrategyStatus } from "@/mocks/types";

const statusStyle: Record<StrategyStatus, { dot: string; text: string; pulse?: boolean }> = {
  LIVE: { dot: "bg-pos", text: "text-pos", pulse: true },
  PAPER: { dot: "bg-info", text: "text-info" },
  DRAFT: { dot: "bg-text-3", text: "text-text-3" },
};

export function StrategyBadge({ status }: { status: StrategyStatus }) {
  const s = statusStyle[status];
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("h-1.5 w-1.5 rounded-full", s.dot, s.pulse && "live-dot")} />
      <span className={cn("mono text-[11px] font-medium tracking-wide", s.text)}>{status}</span>
    </span>
  );
}

const runStyle: Record<BacktestStatus, string> = {
  Completed: "text-pos bg-pos-dim",
  Running: "text-accent bg-accent-dim",
  Failed: "text-neg bg-neg-dim",
  Queued: "text-text-3 bg-raised",
};

export function RunBadge({ status }: { status: BacktestStatus }) {
  return (
    <span
      className={cn(
        "mono inline-flex items-center rounded px-1.5 py-0.5 text-[10.5px] font-medium",
        runStyle[status],
      )}
    >
      {status}
    </span>
  );
}

/** Neutral tag — version chips, symbols, ids */
export function Tag({
  children,
  tone = "default",
  className,
}: {
  children: React.ReactNode;
  tone?: "default" | "accent" | "pos" | "neg";
  className?: string;
}) {
  const tones = {
    default: "text-text-2 bg-raised",
    accent: "text-accent bg-accent-dim",
    pos: "text-pos bg-pos-dim",
    neg: "text-neg bg-neg-dim",
  };
  return (
    <span
      className={cn(
        "mono inline-flex items-center rounded px-1.5 py-0.5 text-[10.5px] font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** Persistent honesty marker — this build runs on synthetic data. */
export function SyntheticTag() {
  return (
    <span
      className="mono inline-flex cursor-default items-center gap-1 rounded border border-edge px-1.5 py-0.5 text-[9.5px] tracking-wider text-text-3 uppercase"
      title="This demo workspace renders synthetic data. No real backtest results are shown."
    >
      <span className="h-1 w-1 rounded-full bg-text-3" />
      Synthetic
    </span>
  );
}
