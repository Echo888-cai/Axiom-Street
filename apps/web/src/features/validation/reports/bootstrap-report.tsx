import { type ValidationRun } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { formatPct } from "@/lib/utils";

export function asInterval(
  raw: unknown,
): { observed: number; low: number; high: number } | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as { observed?: unknown; low?: unknown; high?: unknown };
  if (
    typeof row.observed !== "number" ||
    typeof row.low !== "number" ||
    typeof row.high !== "number"
  ) {
    return null;
  }
  return { observed: row.observed, low: row.low, high: row.high };
}

export function IntervalRow({
  label,
  interval,
  format,
}: {
  label: string;
  interval: { observed: number; low: number; high: number };
  format: (n: number) => string;
}) {
  const span = interval.high - interval.low;
  const absBound = Math.max(
    Math.abs(interval.low),
    Math.abs(interval.high),
    Math.abs(interval.observed),
    1e-9,
  );
  const left = ((interval.low + absBound) / (2 * absBound)) * 100;
  const width = Math.max(4, (span / (2 * absBound)) * 100);
  const obsLeft = ((interval.observed + absBound) / (2 * absBound)) * 100;
  const crosses = interval.low <= 0 && interval.high >= 0;
  return (
    <div className="grid gap-2 sm:grid-cols-[6.5rem_1fr_9rem] sm:items-center">
      <div className="text-[11px] text-as-muted">{label}</div>
      <div className="relative h-2 rounded-full bg-as-secondary">
        <div
          className={`absolute top-0 h-2 rounded-full ${crosses ? "bg-as-negative/70" : "bg-as-primary"}`}
          style={{ left: `${left}%`, width: `${width}%` }}
        />
        <div
          className="absolute top-[-2px] h-3 w-0.5 bg-as-text"
          style={{ left: `${obsLeft}%` }}
          title={`观测 ${format(interval.observed)}`}
        />
      </div>
      <div className="tabular-nums text-[11px] text-as-muted">
        {format(interval.observed)} [{format(interval.low)},{" "}
        {format(interval.high)}]
      </div>
    </div>
  );
}

export function BootstrapReport({ run }: { run: ValidationRun }) {
  const reason =
    typeof run.result.reason === "string" ? run.result.reason : null;
  const sharpe = asInterval(run.result.sharpe);
  const cagr = asInterval(run.result.cagr);
  const maxDd = asInterval(run.result.max_drawdown);
  const nBoot =
    typeof run.result.n_boot === "number" ? run.result.n_boot : null;
  const meanBlock =
    typeof run.result.mean_block_length === "number"
      ? run.result.mean_block_length
      : null;
  const level =
    typeof run.result.confidence_level === "number"
      ? run.result.confidence_level
      : 0.95;
  return (
    <Card>
      <CardHeader
        title="最近一次 Bootstrap"
        hint={
          <p className="text-xs text-as-muted">
            Stationary bootstrap {level * 100}% 分位区间。Sharpe 下界 ≤ 0
            不能进入 VALIDATED。
            {nBoot != null ? ` · ${nBoot} 次重抽样` : ""}
            {meanBlock != null ? ` · 平均块长 ${meanBlock.toFixed(1)}` : ""}
          </p>
        }
      />
      {reason ? (
        <p className="mb-4 text-sm leading-relaxed text-as-text">{reason}</p>
      ) : null}
      <div className="space-y-3">
        {sharpe ? (
          <IntervalRow
            label="Sharpe"
            interval={sharpe}
            format={(n) => n.toFixed(2)}
          />
        ) : null}
        {cagr ? (
          <IntervalRow
            label="CAGR"
            interval={cagr}
            format={(n) => formatPct(n)}
          />
        ) : null}
        {maxDd ? (
          <IntervalRow
            label="MaxDD"
            interval={maxDd}
            format={(n) => formatPct(n)}
          />
        ) : null}
      </div>
    </Card>
  );
}
