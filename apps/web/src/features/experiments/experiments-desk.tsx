"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Beaker } from "lucide-react";
import { api, type ValidationRun } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { useT } from "@/lib/i18n";
import { ValidationLaunch } from "@/features/validation/validation-launch";

function isInflight(row: ValidationRun): boolean {
  return row.status === "QUEUED" || row.status === "RUNNING";
}

function conclusion(row: ValidationRun, t: (key: string) => string) {
  if (row.status === "QUEUED" || row.status === "RUNNING") {
    return { tone: "blue" as const, label: row.progress_step || row.status };
  }
  if (row.error) return { tone: "red" as const, label: t("validation.status.failed") };
  return row.passed
    ? { tone: "green" as const, label: "PBO ≤ 0.5" }
    : { tone: "amber" as const, label: "PBO > 0.5" };
}

type ConfigRow = {
  lookback?: number;
  backtest_id?: string;
  sharpe?: number | null;
};

function asConfigs(result: Record<string, unknown>): ConfigRow[] {
  return Array.isArray(result.configs) ? (result.configs as ConfigRow[]) : [];
}

function PboReport({ run }: { run: ValidationRun }) {
  const t = useT();
  const result: Record<string, unknown> = run.result ?? {};
  const pbo = typeof result.pbo === "number" ? result.pbo : null;
  const nSlices = typeof result.n_slices === "number" ? result.n_slices : null;
  const nCombos =
    typeof result.n_combinations === "number" ? result.n_combinations : null;
  const nObs = typeof result.n_obs_aligned === "number" ? result.n_obs_aligned : null;
  const configs = asConfigs(result);
  const maxAbs = Math.max(0.5, ...configs.map((row) => Math.abs(Number(row.sharpe) || 0)));

  return (
    <Card>
      <CardHeader
        title={t("validation.reports.pbo.title")}
        hint={
          <p className="text-xs text-as-muted">
            {t("validation.reports.pbo.hint")}
          </p>
        }
      />
      <div className="mb-6 flex flex-wrap items-end gap-6">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-as-muted">PBO</div>
          <div
            className={`mt-1 text-3xl font-semibold tabular-nums ${
              pbo != null && pbo > 0.5 ? "text-as-negative" : "text-as-text"
            }`}
          >
            {pbo == null ? "—" : pbo.toFixed(2)}
          </div>
        </div>
        <p className="max-w-xl text-sm leading-relaxed text-as-muted">
          {nSlices != null
            ? `${nSlices} ${t("validation.reports.pbo.slicesUnit")}`
            : t("validation.reports.pbo.slicesUnrecorded")}
          {nCombos != null
            ? ` · ${nCombos} ${t("validation.reports.pbo.combosUnit")}`
            : ""}
          {nObs != null ? ` · ${nObs} ${t("validation.reports.commonDays")}` : ""}
        </p>
      </div>
      {configs.length ? (
        <div className="space-y-2">
          {configs.map((row) => {
            const sharpe = Number(row.sharpe) || 0;
            const width = Math.max(8, Math.min(100, (Math.abs(sharpe) / maxAbs) * 100));
            return (
              <div
                key={`${row.lookback}-${row.backtest_id}`}
                className="grid gap-2 sm:grid-cols-[7.5rem_1fr] sm:items-center"
              >
                <div className="text-[11px] text-as-muted">
                  <div className="font-medium tabular-nums text-as-text">
                    lookback {row.lookback ?? "—"}
                  </div>
                  {row.backtest_id ? (
                    <Link
                      href={`/backtests/${row.backtest_id}`}
                      className="text-as-primary hover:underline"
                    >
                      {row.backtest_id.slice(0, 8)}…
                    </Link>
                  ) : null}
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-2 flex-1 rounded-full bg-as-secondary">
                    <div
                      className={`h-2 rounded-full ${sharpe < 0 ? "bg-as-negative" : "bg-as-primary"}`}
                      style={{ width: `${width}%` }}
                    />
                  </div>
                  <span className="w-14 shrink-0 text-right text-xs tabular-nums text-as-text">
                    {row.sharpe == null ? "—" : sharpe.toFixed(2)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </Card>
  );
}

export function ExperimentsDesk() {
  const t = useT();
  const { data, isLoading, error } = useQuery({
    queryKey: ["pbo-runs"],
    queryFn: () => api.listValidation({ kind: "PBO" }),
    refetchInterval: (query) => {
      const rows = query.state.data?.items ?? [];
      return rows.some(isInflight) ? 2000 : false;
    },
  });

  const items = data?.items ?? [];
  const latest = items[0];

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        title={t("validation.experiments.title")}
        description={t("validation.experiments.description")}
      />

      <Card>
        <CardHeader
          title={t("validation.experiments.scanTitle")}
          hint={
            <p className="text-xs text-as-muted">
              {t("validation.experiments.scanHintBefore")}{" "}
              <Link href="/validation" className="text-as-primary hover:underline">
                {t("validation.experiments.validationLink")}
              </Link>
              {t("validation.experiments.scanHintAfter")}
            </p>
          }
        />
        <ValidationLaunch kinds={["pbo"]} />
      </Card>

      {latest && (latest.status === "COMPLETED" || latest.error) ? <PboReport run={latest} /> : null}

      {isLoading ? (
        <Card className="h-40 animate-pulse bg-as-secondary" />
      ) : error ? (
        <Card>
          <EmptyState
            title={t("validation.errors.apiOffline")}
            description={t("validation.errors.apiOfflineHint")}
          />
        </Card>
      ) : !items.length ? (
        <Card className="min-h-[240px]">
          <EmptyState
            icon={Beaker}
            title={t("validation.experiments.noScansTitle")}
            description={t("validation.experiments.noScansDescription")}
          />
        </Card>
      ) : (
        <Card className="p-0">
          <div className="border-b border-as-border px-5 py-3 text-sm font-medium">
            {t("validation.experiments.scansHeading")}
          </div>
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-as-muted">
              <tr className="border-b border-as-border">
                <th className="px-5 py-2 font-medium">
                  {t("validation.table.status")}
                </th>
                <th className="px-5 py-2 font-medium">
                  {t("validation.table.conclusion")}
                </th>
                <th className="px-5 py-2 font-medium">PBO</th>
                <th className="px-5 py-2 font-medium">
                  {t("validation.table.grid")}
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => {
                const result: Record<string, unknown> = row.result ?? {};
                const params: Record<string, unknown> = row.params ?? {};
                const badge = conclusion(row, t);
                const pbo = typeof result.pbo === "number" ? result.pbo : null;
                const values = Array.isArray(params.values)
                  ? (params.values as number[]).join(", ")
                  : "—";
                return (
                  <tr key={row.id} className="border-b border-as-border last:border-0">
                    <td className="px-5 py-3 text-xs text-as-muted">{row.status}</td>
                    <td className="px-5 py-3">
                      <Badge tone={badge.tone}>{badge.label}</Badge>
                      {row.error?.message ? (
                        <p className="mt-1 text-xs text-as-muted">{row.error.message}</p>
                      ) : null}
                    </td>
                    <td className="px-5 py-3 tabular-nums text-as-muted">
                      {pbo == null ? "—" : pbo.toFixed(2)}
                    </td>
                    <td className="px-5 py-3 tabular-nums text-as-muted">{values}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
