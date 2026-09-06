"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BadgeCheck } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { formatPct } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { ValidationLaunch } from "./validation-launch";
import { isInflight, conclusion } from "./validation-status";
import { WalkForwardReport } from "./reports/walk-forward-report";
import { SensitivityReport } from "./reports/sensitivity-report";
import { asInterval, BootstrapReport } from "./reports/bootstrap-report";
import { RegimeReport } from "./reports/regime-report";
import { SpaReport } from "./reports/spa-report";
import { CostReport } from "./reports/cost-report";

export function ValidationDesk() {
  const t = useT();
  const { data, isLoading, error } = useQuery({
    queryKey: ["validation-runs"],
    queryFn: () => api.listValidation(),
    refetchInterval: (query) => {
      const rows = query.state.data?.items ?? [];
      return rows.some(isInflight) ? 2000 : false;
    },
  });

  const gates = data?.gates;
  const items = data?.items ?? [];
  const latestWalk = items.find((row) => row.kind === "WALK_FORWARD");
  const latestSens = items.find((row) => row.kind === "SENSITIVITY");
  const latestCost = items.find((row) => row.kind === "COST");
  const latestBoot = items.find((row) => row.kind === "BOOTSTRAP");
  const latestRegime = items.find((row) => row.kind === "REGIME");
  const latestSpa = items.find((row) => row.kind === "SPA");

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        title={t("validation.desk.title")}
        description={t("validation.desk.description")}
      />

      <Card>
        <p className="text-sm text-as-text">
          {gates?.note ||
            (error
              ? t("validation.desk.gatesError")
              : t("validation.desk.gatesLoading"))}
        </p>
        <dl className="mt-4 grid gap-3 text-xs text-as-muted sm:grid-cols-3">
          <div>
            <dt className="text-[11px] uppercase tracking-wide">
              {t("validation.desk.implemented")}
            </dt>
            <dd className="mt-1 text-as-text">
              {(
                gates?.available || [
                  "DSR",
                  "WALK_FORWARD",
                  "PBO",
                  "SENSITIVITY",
                  "COST",
                  "BOOTSTRAP",
                  "REGIME",
                  "SPA",
                ]
              ).join(" · ")}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide">
              {t("validation.desk.validatedRequires")}
            </dt>
            <dd className="mt-1 text-as-text">
              {(
                gates?.validated_requires || [
                  "WALK_FORWARD",
                  "DSR",
                  "PBO",
                  "SENSITIVITY",
                  "COST",
                  "BOOTSTRAP",
                  "REGIME",
                  "SPA",
                ]
              ).join(" · ")}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide">
              {t("validation.desk.notYetConnected")}
            </dt>
            <dd className="mt-1">
              {(gates?.missing || []).join(" · ") || "—"}
            </dd>
          </div>
        </dl>
      </Card>

      <Card>
        <CardHeader
          title={t("validation.form.submit")}
          hint={
            <p className="text-xs text-as-muted">
              {t("validation.desk.launchHintBefore")}{" "}
              <Link href="/experiments" className="text-as-primary hover:underline">
                {t("validation.experiments.title")}
              </Link>
              {t("validation.desk.launchHintAfter")}
            </p>
          }
        />
        <ValidationLaunch />
      </Card>

      {latestWalk && (latestWalk.status === "COMPLETED" || latestWalk.error) ? (
        <WalkForwardReport run={latestWalk} />
      ) : null}
      {latestSens && (latestSens.status === "COMPLETED" || latestSens.error) ? (
        <SensitivityReport run={latestSens} />
      ) : null}
      {latestCost && (latestCost.status === "COMPLETED" || latestCost.error) ? (
        <CostReport run={latestCost} />
      ) : null}
      {latestBoot && (latestBoot.status === "COMPLETED" || latestBoot.error) ? (
        <BootstrapReport run={latestBoot} />
      ) : null}
      {latestRegime &&
      (latestRegime.status === "COMPLETED" || latestRegime.error) ? (
        <RegimeReport run={latestRegime} />
      ) : null}
      {latestSpa && (latestSpa.status === "COMPLETED" || latestSpa.error) ? (
        <SpaReport run={latestSpa} />
      ) : null}

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
            icon={BadgeCheck}
            title={t("validation.desk.noRunsTitle")}
            description={t("validation.desk.noRunsDescription")}
          />
        </Card>
      ) : (
        <Card className="p-0">
          <div className="border-b border-as-border px-5 py-3 text-sm font-medium">
            {t("validation.desk.runsHeading")}
          </div>
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-as-muted">
              <tr className="border-b border-as-border">
                <th className="px-5 py-2 font-medium">
                  {t("validation.table.type")}
                </th>
                <th className="px-5 py-2 font-medium">
                  {t("validation.table.status")}
                </th>
                <th className="px-5 py-2 font-medium">
                  {t("validation.table.conclusion")}
                </th>
                <th className="px-5 py-2 font-medium">
                  {t("validation.table.summary")}
                </th>
                <th className="px-5 py-2 font-medium">
                  {t("validation.table.backtest")}
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => {
                const badge = conclusion(row);
                const pbo =
                  typeof row.result.pbo === "number" ? row.result.pbo : null;
                const dsr =
                  typeof row.result.dsr === "number" ? row.result.dsr : null;
                const n =
                  typeof row.result.n_trials === "number"
                    ? row.result.n_trials
                    : null;
                const oos =
                  typeof row.result.combined_oos_sharpe === "number"
                    ? row.result.combined_oos_sharpe
                    : null;
                const shape =
                  typeof row.result.shape === "string"
                    ? row.result.shape
                    : null;
                const breakeven =
                  typeof row.result.breakeven_bps === "number"
                    ? row.result.breakeven_bps
                    : null;
                const sharpeCi = asInterval(row.result.sharpe);
                const concentrated =
                  typeof row.result.concentrated_in === "string"
                    ? row.result.concentrated_in
                    : null;
                const summary =
                  row.kind === "DSR"
                    ? `${dsr == null ? "—" : formatPct(dsr)}${n != null ? ` · N=${n}` : ""}`
                    : row.kind === "PBO"
                      ? pbo == null
                        ? "—"
                        : `PBO ${pbo.toFixed(2)}`
                      : row.kind === "SENSITIVITY"
                        ? shape == null
                          ? "—"
                          : shape === "plateau"
                            ? t("validation.shapes.plateau")
                            : t("validation.shapes.knifeEdge")
                        : row.kind === "COST"
                          ? breakeven == null && row.passed
                            ? t("validation.reports.cost.aboveGrid")
                            : breakeven == null
                              ? "—"
                              : `${breakeven.toFixed(1)} bps`
                          : row.kind === "BOOTSTRAP"
                            ? sharpeCi
                              ? `${sharpeCi.observed.toFixed(2)} [${sharpeCi.low.toFixed(2)}, ${sharpeCi.high.toFixed(2)}]`
                              : "—"
                            : row.kind === "REGIME"
                              ? concentrated
                                ? `${t("validation.desk.concentrated")} ${concentrated}`
                                : row.passed
                                  ? t("validation.desk.acrossRegimes")
                                  : t("validation.results.failed")
                              : row.kind === "SPA"
                                ? typeof row.result.p_spa_consistent ===
                                  "number"
                                  ? `SPA_c ${row.result.p_spa_consistent.toFixed(3)}`
                                  : "—"
                                : oos == null
                                  ? "—"
                                  : `OOS Sharpe ${oos.toFixed(2)}`;
                return (
                  <tr
                    key={row.id}
                    className="border-b border-as-border last:border-0"
                  >
                    <td className="px-5 py-3 font-medium">{row.kind}</td>
                    <td className="px-5 py-3 text-xs text-as-muted">
                      {row.status}
                    </td>
                    <td className="px-5 py-3">
                      <Badge tone={badge.tone}>{badge.label}</Badge>
                      {row.error?.message ? (
                        <p className="mt-1 text-xs text-as-muted">
                          {row.error.message}
                        </p>
                      ) : null}
                    </td>
                    <td className="px-5 py-3 tabular-nums text-as-muted">
                      {summary}
                    </td>
                    <td className="px-5 py-3">
                      {row.backtest_id ? (
                        <Link
                          href={`/backtests/${row.backtest_id}`}
                          className="text-as-primary hover:underline"
                        >
                          {row.backtest_id.slice(0, 8)}…
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
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
