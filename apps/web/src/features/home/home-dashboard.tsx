"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Database, FlaskConical, LineChart, RefreshCw, Shield } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { KpiStrip } from "@/components/home/kpi-strip";
import { Badge } from "@/components/ui/badge";
import { EquityCurve } from "@/components/charts/equity-curve";
import { Tabs } from "@/components/ui/tabs";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Backtest, type Strategy } from "@/lib/api";
import { BACKTEST_TONE, labelStatus } from "@/lib/labels";
import { filterEquityByPeriod, formatPct } from "@/lib/utils";

const PERIODS = [
  { id: "1M", label: "1月" },
  { id: "3M", label: "3月" },
  { id: "YTD", label: "今年" },
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
  const [hello, setHello] = useState("你好");
  const [period, setPeriod] = useState<(typeof PERIODS)[number]["id"]>("ALL");
  const hasResearch = strategies.length > 0 || backtests.length > 0;
  const completed = backtests.filter((b) => b.status === "COMPLETED");
  const latest = completed[0];

  useEffect(() => {
    const h = new Date().getHours();
    setHello(h < 12 ? "早上好" : h < 18 ? "下午好" : "晚上好");
  }, []);

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

  const equityPoints = useMemo(() => {
    const raw = (equity.data || []).map((p) => ({
      time: p.ts,
      strategy: p.strategy_value,
      benchmark: p.benchmark_value,
    }));
    return filterEquityByPeriod(raw, period);
  }, [equity.data, period]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-16 w-80" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Skeleton className="h-[108px]" />
          <Skeleton className="h-[108px]" />
          <Skeleton className="h-[108px]" />
          <Skeleton className="h-[108px]" />
        </div>
        <Skeleton className="h-[360px]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6 aq-enter">
        <PageHeader
          title={hello}
          description="研究工作台需要本地 API 才能读取策略与回测。"
        />
        <Card className="min-h-[280px]">
          <EmptyState
            icon={Database}
            title="无法连接研究引擎"
            description="请启动 FastAPI（端口 8000），然后刷新。侧栏会显示连接状态。"
            action={
              <Button size="sm" onClick={onRetry}>
                重试连接
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  if (!hasResearch) {
    return (
      <div className="space-y-8 aq-enter">
        <PageHeader
          title={hello}
          description="从一条可验证的假设开始。数字来自冻结数据与固定引擎，不是实盘组合。"
        />
        <Card className="overflow-hidden p-0">
          <div className="grid gap-0 lg:grid-cols-3">
            {[
              { n: "01", title: "创建策略", body: "用 SPY 200 日均线模板记录假设。" },
              { n: "02", title: "拉取行情", body: "Yahoo 失败时回退 Stooq，无需 API Key。" },
              { n: "03", title: "运行回测", body: "收盘信号、下一根 K 线成交、5 bps 滑点。" },
            ].map((step, i) => (
              <div
                key={step.n}
                className={`p-8 ${i < 2 ? "border-b border-aq-border lg:border-b-0 lg:border-r" : ""}`}
              >
                <div className="text-[11px] font-medium tracking-wider text-aq-primary">{step.n}</div>
                <div className="mt-3 text-base font-medium text-aq-text">{step.title}</div>
                <p className="mt-2 text-sm leading-relaxed text-aq-muted">{step.body}</p>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3 border-t border-aq-border bg-aq-secondary/40 px-8 py-4">
            <Link href="/strategies">
              <Button>打开策略实验室</Button>
            </Link>
            <Link href="/settings">
              <Button variant="secondary">去设置拉取 SPY</Button>
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 aq-enter">
      <PageHeader
        title={hello}
        description="研究工作台。这里的数字来自可复现回测，不是实盘组合。"
        action={
          <Button variant="secondary" size="sm" onClick={() => qc.invalidateQueries()}>
            <RefreshCw className="h-3.5 w-3.5" />
            刷新数据
          </Button>
        }
      />

      <KpiStrip
        hasBacktest={Boolean(latest)}
        totalReturn={latest?.total_return ?? metrics.data?.total_return ?? null}
        sharpe={latest?.sharpe ?? metrics.data?.sharpe ?? null}
        maxDrawdown={latest?.max_drawdown ?? metrics.data?.max_drawdown ?? null}
        strategyCount={strategies.length}
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="min-h-[360px] xl:col-span-2">
          <CardHeader
            title={latest ? "最近一次回测权益" : "权益曲线"}
            action={
              latest ? (
                <Tabs
                  value={period}
                  onChange={(id) => setPeriod(id as typeof period)}
                  items={PERIODS.map((p) => ({ id: p.id, label: p.label }))}
                />
              ) : null
            }
          />
          {latest && equityPoints.length > 0 ? (
            <EquityCurve data={equityPoints} />
          ) : latest ? (
            <div className="flex h-[280px] items-center justify-center">
              <Skeleton className="h-[240px] w-full" />
            </div>
          ) : (
            <EmptyState
              icon={LineChart}
              title="还没有回测权益曲线"
              description="从可复现的 SPY 200 日均线回测开始。"
              action={
                <Link href="/strategies">
                  <Button size="sm">打开策略实验室</Button>
                </Link>
              }
            />
          )}
        </Card>

        <Card className="min-h-[360px]">
          <CardHeader
            title="活跃策略"
            action={
              <Link href="/strategies" className="text-xs text-aq-primary hover:underline">
                查看全部
              </Link>
            }
          />
          {strategies.length === 0 ? (
            <EmptyState icon={FlaskConical} title="还没有策略" description="先创建 SPY 200 日均线策略。" />
          ) : (
            <ul className="space-y-1">
              {strategies.slice(0, 5).map((s) => (
                <li key={s.id}>
                  <Link
                    href={`/strategies/${s.id}`}
                    className="flex items-center justify-between gap-3 rounded-lg px-1 py-2.5 hover:bg-aq-secondary"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-aq-text">{s.name}</div>
                      <div className="text-[11px] text-aq-muted">{labelStatus(s.status)}</div>
                    </div>
                    <Badge tone="blue">{s.benchmark}</Badge>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="min-h-[220px]">
          <CardHeader
            title="最近回测"
            action={
              <Link href="/backtests" className="text-xs text-aq-primary hover:underline">
                查看全部
              </Link>
            }
          />
          {backtests.length === 0 ? (
            <EmptyState icon={LineChart} title="还没有回测" description="跑完第一次回测后，结果会显示在这里。" />
          ) : (
            <ul className="space-y-1">
              {backtests.slice(0, 5).map((b) => (
                <li key={b.id}>
                  <Link
                    href={`/backtests/${b.id}`}
                    className="flex items-center justify-between gap-3 rounded-lg px-1 py-2.5 hover:bg-aq-secondary"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-aq-text">
                        {b.strategy_name || `${b.start_date} → ${b.end_date}`}
                      </div>
                      <div className="text-[11px] text-aq-muted">
                        {b.start_date} → {b.end_date}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {b.status === "COMPLETED" && b.total_return != null ? (
                        <span
                          className={`hidden text-xs tabular sm:block ${
                            b.total_return >= 0 ? "text-aq-positive" : "text-aq-negative"
                          }`}
                        >
                          {formatPct(b.total_return)}
                        </span>
                      ) : null}
                      <Badge tone={BACKTEST_TONE[b.status] || "blue"}>{labelStatus(b.status)}</Badge>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="min-h-[220px]">
          <CardHeader title="研究清单" />
          <ul className="space-y-3 text-sm">
            {[
              { done: strategies.length > 0, label: "创建 SPY 200 日均线策略", href: "/strategies" },
              { done: completed.length > 0, label: "跑通第一次可复现回测" },
              {
                done: completed.length > 0,
                label: "查看成交与回撤",
                href: completed[0] ? `/backtests/${completed[0].id}` : undefined,
              },
            ].map((item) => (
              <li key={item.label} className="flex items-start gap-2 text-aq-muted">
                <span
                  className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
                    item.done ? "border-aq-positive bg-aq-positive text-white" : "border-aq-border"
                  }`}
                >
                  {item.done ? <Check className="h-3 w-3" /> : null}
                </span>
                {item.href ? (
                  <Link href={item.href} className="hover:text-aq-text">
                    {item.label}
                  </Link>
                ) : (
                  <span>{item.label}</span>
                )}
              </li>
            ))}
          </ul>
        </Card>

        <Card className="min-h-[220px]">
          <CardHeader
            title="风险快照"
            action={
              <Link href="/risk" className="text-xs text-aq-primary hover:underline">
                查看完整风控
              </Link>
            }
          />
          <EmptyState
            icon={Shield}
            title="暂无实盘风险暴露"
            description="硬风控与一键停机将在模拟/实盘阶段上线。"
          />
        </Card>
      </div>
    </div>
  );
}
