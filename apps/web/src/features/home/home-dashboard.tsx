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
import { ResearchHero } from "./research-hero";
import { ResearchPath } from "./research-path";
import { RecentResearch } from "./recent-research";

const PERIODS = [
  { id: "1M", label: "1月" },
  { id: "3M", label: "3月" },
  { id: "1Y", label: "1年" },
  { id: "ALL", label: "全部" },
] as const;

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
  const [period, setPeriod] = useState<(typeof PERIODS)[number]["id"]>("ALL");
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
  return (
    <div className="space-y-7 as-enter">
      <PageHeader
        title="研究概览"
        description="保持好奇，保持严谨。欢迎回到你的研究空间。"
        action={
          <>
            <span className="mr-2 hidden items-center gap-2 text-[11px] text-as-muted xl:flex">
              <CalendarDays className="h-3.5 w-3.5" /> 研究工作台
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => qc.invalidateQueries()}
              aria-label="刷新研究数据"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
            <Link
              href="/strategies"
              className="as-button-primary inline-flex min-h-9 items-center gap-2 rounded-xl px-3.5 text-xs font-medium text-white"
            >
              <Plus className="h-3.5 w-3.5" /> 新建研究
            </Link>
          </>
        }
      />
      <ResearchHero />
      {error && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-3 rounded-xl border border-as-border bg-white/70 px-4 py-3 text-xs"
        >
          <WifiOff className="h-4 w-4 text-as-muted" />
          <span className="flex-1 text-as-muted">
            研究服务暂未连接，连接恢复后将自动同步你的数据。
          </span>
          <Button variant="ghost" size="sm" onClick={onRetry}>
            重新连接 <RefreshCw className="h-3 w-3" />
          </Button>
          <Link href="/settings" className="text-as-primary">
            检查设置
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
          unavailable={error && !strategies.length}
        />
      )}
      <div className="grid gap-5 xl:grid-cols-[1.8fr_1fr]">
        <Card className="min-w-0 overflow-hidden">
          <CardHeader
            title="研究表现"
            hint={
              <p className="mt-1 text-[11px] text-as-muted">
                {latest
                  ? `${latest.strategy_name || "最近完成回测"} · ${latest.start_date} — ${latest.end_date}`
                  : "最近一次完成回测的权益走势"}
              </p>
            }
            action={
              latest ? (
                <Tabs
                  value={period}
                  onChange={(id) => setPeriod(id as typeof period)}
                  items={[...PERIODS]}
                />
              ) : (
                <span className="rounded-full border border-as-border px-2.5 py-1 text-[10px] text-as-muted">
                  等待回测
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
                    ? "权益数据暂时无法读取"
                    : latest
                      ? "此区间暂无权益数据"
                      : "给想法一点时间，让数据描绘答案"}
                </h3>
                <p className="mt-2 max-w-xs text-[11px] leading-5 text-as-muted">
                  {latest
                    ? "尝试切换时间范围，或重新读取回测结果。"
                    : "完成首次回测后，权益曲线与基准表现将在这里呈现。"}
                </p>
                {equity.isError ? (
                  <Button
                    className="mt-4"
                    size="sm"
                    variant="secondary"
                    onClick={() => equity.refetch()}
                  >
                    重新读取
                  </Button>
                ) : (
                  <Link
                    href={latest ? `/backtests/${latest.id}` : "/strategies"}
                    className="mt-4 flex items-center gap-1.5 text-[11px] text-as-primary"
                  >
                    {latest ? "查看回测详情" : "开始第一次回测"}
                    <ArrowUpRight className="h-3 w-3" />
                  </Link>
                )}
              </div>
            </div>
          )}
          <div className="mt-4 flex items-start gap-1.5 border-t border-as-border pt-3 text-[10px] leading-4 text-as-muted">
            <CircleHelp className="mt-0.5 h-3 w-3 shrink-0" />
            历史回测用于研究假设，不代表实盘表现。
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
