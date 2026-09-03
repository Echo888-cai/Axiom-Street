import Link from "next/link";

type Point = {
  value?: number;
  sharpe?: number | null;
  backtest_id?: string | null;
  on_plateau?: boolean;
  is_peak?: boolean;
};

function widthPct(value: number, maxAbs: number): number {
  if (maxAbs <= 0) return 8;
  return Math.max(8, Math.min(100, (Math.abs(value) / maxAbs) * 100));
}

export function SharpeSurfaceBars({ points }: { points: Point[] }) {
  const maxAbs = Math.max(0.5, ...points.map((row) => Math.abs(Number(row.sharpe) || 0)));

  return (
    <div className="space-y-2">
      {points.map((row) => {
        const sharpe = Number(row.sharpe) || 0;
        const width = widthPct(sharpe, maxAbs);
        const tone = row.is_peak
          ? sharpe < 0
            ? "bg-as-negative"
            : "bg-as-primary"
          : row.on_plateau
            ? "bg-as-positive"
            : sharpe < 0
              ? "bg-as-negative"
              : "bg-as-muted/40";
        return (
          <div
            key={`${row.value}-${row.backtest_id}`}
            className="grid gap-2 sm:grid-cols-[7.5rem_1fr] sm:items-center"
          >
            <div className="text-[11px] text-as-muted">
              <div className="font-medium tabular-nums text-as-text">
                lookback {row.value ?? "—"}
                {row.is_peak ? " · 峰" : row.on_plateau ? " · 高原" : ""}
              </div>
              {row.backtest_id ? (
                <Link href={`/backtests/${row.backtest_id}`} className="text-as-primary hover:underline">
                  {row.backtest_id.slice(0, 8)}…
                </Link>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              <div className="h-2 flex-1 rounded-full bg-as-secondary">
                <div className={`h-2 rounded-full ${tone}`} style={{ width: `${width}%` }} />
              </div>
              <span className="w-14 shrink-0 text-right text-xs tabular-nums text-as-text">
                {row.sharpe == null ? "—" : sharpe.toFixed(2)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

type CostPoint = {
  cost_bps?: number;
  alpha_capm?: number | null;
  backtest_id?: string | null;
};

export function CostAlphaBars({
  points,
  realisticBps,
}: {
  points: CostPoint[];
  realisticBps?: number | null;
}) {
  const maxAbs = Math.max(0.01, ...points.map((row) => Math.abs(Number(row.alpha_capm) || 0)));

  return (
    <div className="space-y-2">
      {points.map((row) => {
        const alpha = Number(row.alpha_capm) || 0;
        const width = widthPct(alpha, maxAbs);
        const atRealistic =
          realisticBps != null && Number(row.cost_bps) === Number(realisticBps);
        return (
          <div
            key={`${row.cost_bps}-${row.backtest_id}`}
            className="grid gap-2 sm:grid-cols-[7.5rem_1fr] sm:items-center"
          >
            <div className="text-[11px] text-as-muted">
              <div className="font-medium tabular-nums text-as-text">
                {row.cost_bps == null ? "—" : `${row.cost_bps} bps`}
                {atRealistic ? " · 真实" : ""}
              </div>
              {row.backtest_id ? (
                <Link href={`/backtests/${row.backtest_id}`} className="text-as-primary hover:underline">
                  {row.backtest_id.slice(0, 8)}…
                </Link>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              <div className="h-2 flex-1 rounded-full bg-as-secondary">
                <div
                  className={`h-2 rounded-full ${alpha < 0 ? "bg-as-negative" : "bg-as-primary"}`}
                  style={{ width: `${width}%` }}
                />
              </div>
              <span className="w-16 shrink-0 text-right text-xs tabular-nums text-as-text">
                {row.alpha_capm == null ? "—" : alpha.toFixed(3)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
