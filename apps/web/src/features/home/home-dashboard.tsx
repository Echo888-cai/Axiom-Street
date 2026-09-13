"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  CalendarDays,
  CircleHelp,
  LineChart,
  RefreshCw,
  Plus,
  WifiOff,
} from "lucide-react";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { KpiStrip } from "@/components/home/kpi-strip";
import { EquityCurve } from "@/components/charts/equity-curve";
import { Tabs } from "@/components/ui/tabs";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Backtest, type Strategy } from "@/lib/api";
import { filterEquityByPeriod } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { ResearchHero } from "./research-hero";
import { ResearchPath } from "./research-path";
import { RecentResearch } from "./recent-research";

const PERIODS = ["1M", "3M", "1Y", "ALL"] as const;

export function HomeDashboard({
  strategies,
  backtests,
  loading,
  error,
  onRetry,
}: {
  strategies: Strategy[];
  backtests: Backtest[];
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
}) {
  const qc = useQueryClient();
  const t = useT();
  const [period, setPeriod] = useState<(typeof PERIODS)[number]>("ALL");
  const latest = [...backtests]
    .filter((b) => b.status === "COMPLETED")
    .sort((a, b) =>
      (b.finished_at || b.created_at).localeCompare(
        a.finished_at || a.created_at,
      ),
    )[0];
  const equity = useQuery({
    queryKey: ["equity", latest?.id],
    queryFn: () => api.getEquity(latest!.id),
    enabled: Boolean(latest),
  });
  const metrics = useQuery({
    queryKey: ["metrics", latest?.id],
    queryFn: () => api.getMetrics(latest!.id),
    enabled: Boolean(latest),
  });
  const equityPoints = useMemo(
    () =>
      filterEquityByPeriod(
        (equity.data || []).map((p) => ({
          time: p.ts,
          strategy: p.strategy_value,
          benchmark: p.benchmark_value,
        })),
        period,
      ),
    [equity.data, period],
  );
  const periodItems = PERIODS.map((id) => ({
    id,
    label: t(`common.overview.period.${id}`),
  }));
  return (
    <div className="space-y-8 as-enter">
      <PageHeader
        title={t("common.overview.title")}
        description="研究进展，一目了然。"
        action={
          <>
            <span className="mr-2 hidden items-center gap-2 text-xs text-as-muted xl:flex">
              <CalendarDays className="h-3.5 w-3.5" /> {t("common.overview.workspaceTag")}
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => qc.invalidateQueries()}
              aria-label={t("common.overview.refreshAria")}
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
            <Link
              href="/strategies"
              className="as-button-primary inline-flex min-h-11 items-center gap-2 rounded-xl px-4 text-[13px] font-medium text-white"
            >
              <Plus className="h-3.5 w-3.5" /> {t("common.overview.newResearch")}
            </Link>
          </>
        }
      />
      <ResearchHero compact={loading || error || strategies.length > 0} />
      {error && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-3 rounded-xl border border-as-border bg-white/70 px-4 py-3 text-xs"
        >
          <WifiOff className="h-4 w-4 text-as-muted" />
          <span className="flex-1 text-as-muted">
            {t("common.overview.serviceDown")}
          </span>
          <Button variant="ghost" size="sm" onClick={onRetry}>
            {t("common.reconnect")} <RefreshCw className="h-3 w-3" />
          </Button>
          <Link href="/settings" className="text-as-primary">
            {t("common.overview.checkSettings")}
          </Link>
        </div>
      )}
      {loading ? (
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[132px]" />
          ))}
        </div>
      ) : (
        <KpiStrip
          hasBacktest={Boolean(latest)}
          totalReturn={
            latest?.total_return ?? metrics.data?.total_return ?? null
          }
          sharpe={latest?.sharpe ?? metrics.data?.sharpe ?? null}
          maxDrawdown={
            latest?.max_drawdown ?? metrics.data?.max_drawdown ?? null
          }
          strategyCount={strategies.length}
          unavailable={error}
        />
      )}
      <div className="grid gap-6 xl:grid-cols-[1.8fr_1fr]">
        <Card className="min-w-0 overflow-hidden">
          <CardHeader
            title={t("common.overview.performance")}
            hint={
              <p className="mt-1 text-xs text-as-muted">
                {latest
                  ? `${latest.strategy_name || t("common.overview.recentBacktestName")} · ${latest.start_date} — ${latest.end_date}`
                  : t("common.overview.latestBacktestHint")}
              </p>
            }
            action={
              latest ? (
                <Tabs
                  value={period}
                  onChange={(id) => setPeriod(id as typeof period)}
                  items={[...periodItems]}
                />
              ) : (
                <span className="rounded-full border border-as-border px-2.5 py-1 text-[11px] text-as-muted">
                  {t("common.overview.waitingBacktest")}
                </span>
              )
            }
          />
          {latest && equityPoints.length > 0 ? (
            <EquityCurve data={equityPoints} height={258} />
          ) : loading || (latest && equity.isLoading) ? (
            <Skeleton className="h-[278px]" />
          ) : (
            <div className="as-grid-paper relative flex h-[262px] items-center justify-center overflow-hidden rounded-xl border border-as-border/50">
              <div className="absolute inset-0 bg-gradient-to-b from-white/20 via-white/80 to-white" />
              <div className="relative flex flex-col items-center px-5 text-center">
                <span className="as-icon-well mb-4 h-12 w-12 rounded-2xl">
                  <LineChart className="h-5 w-5" strokeWidth={1.5} />
                </span>
                <h3 className="text-sm font-medium">
                  {equity.isError
                    ? t("common.overview.equityReadError")
                    : latest
                      ? t("common.overview.equityEmptyForPeriod")
                      : t("common.overview.equityEmpty")}
                </h3>
                <p className="mt-2 max-w-xs text-xs leading-5 text-as-muted">
                  {latest
                    ? t("common.overview.switchPeriodHint")
                    : t("common.overview.completeFirstHint")}
                </p>
                {equity.isError ? (
                  <Button
                    className="mt-4"
                    size="sm"
                    variant="secondary"
                    onClick={() => equity.refetch()}
                  >
                    {t("common.overview.reload")}
                  </Button>
                ) : (
                  <Link
                    href={latest ? `/backtests/${latest.id}` : "/strategies"}
                    className="mt-4 flex items-center gap-1.5 text-xs text-as-primary"
                  >
                    {latest
                      ? t("common.overview.viewBacktest")
                      : t("common.overview.startFirstBacktest")}
                    <ArrowUpRight className="h-3 w-3" />
                  </Link>
                )}
              </div>
            </div>
          )}
          <div className="mt-4 flex items-start gap-1.5 border-t border-as-border pt-3 text-[11px] leading-4 text-as-muted">
            <CircleHelp className="mt-0.5 h-3 w-3 shrink-0" />
            {t("common.overview.disclaimer")}
          </div>
        </Card>
        <ResearchPath
          hasStrategy={strategies.length > 0}
          hasBacktest={Boolean(latest)}
        />
      </div>
      <RecentResearch
        strategies={strategies}
        backtests={backtests}
        loading={loading}
        unavailable={error}
      />
    </div>
  );
}
