"use client";

import { type ValidationRun } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { formatPct } from "@/lib/utils";
import { useT } from "@/lib/i18n";

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
  const t = useT();
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
          title={`${t("validation.reports.bootstrap.observed")} ${format(interval.observed)}`}
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
  const t = useT();
  const result: Record<string, unknown> = run.result ?? {};
  const reason =
    typeof result.reason === "string" ? result.reason : null;
  const sharpe = asInterval(result.sharpe);
  const cagr = asInterval(result.cagr);
  const maxDd = asInterval(result.max_drawdown);
  const nBoot =
    typeof result.n_boot === "number" ? result.n_boot : null;
  const meanBlock =
    typeof result.mean_block_length === "number"
      ? result.mean_block_length
      : null;
  const level =
    typeof result.confidence_level === "number"
      ? result.confidence_level
      : 0.95;
  return (
    <Card>
      <CardHeader
        title={t("validation.reports.bootstrap.title")}
        hint={
          <p className="text-xs text-as-muted">
            {`Stationary bootstrap ${level * 100}% ${t("validation.reports.bootstrap.percentile")} Sharpe ${t("validation.reports.bootstrap.lowerBound")} ≤ 0 ${t("validation.reports.bootstrap.noEnter")}`}
            {nBoot != null ? ` · ${nBoot} ${t("validation.reports.bootstrap.resampleSuffix")}` : ""}
            {meanBlock != null ? ` · ${t("validation.reports.bootstrap.meanBlockPrefix")} ${meanBlock.toFixed(1)}` : ""}
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
