"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Copy, Download, LineChart } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { EquityCurve } from "@/components/charts/equity-curve";
import { DrawdownChart } from "@/components/charts/drawdown-chart";
import { MonthlyHeatmap } from "@/components/charts/monthly-heatmap";
import { formatNumber, formatPct, formatUsd, filterEquityByPeriod } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs } from "@/components/ui/tabs";
import { ProgressSteps } from "@/components/ui/progress-steps";
import { MetricTile, metricTone } from "@/components/ui/metric-tile";
import { toast } from "@/components/ui/toast";
import { labelDirection, labelStatus, labelStep } from "@/lib/labels";

const RUN_STEPS = ["排队中", "准备环境", "加载数据", "运行策略", "计算指标"];

export function BacktestStudio({ backtestId }: { backtestId: string }) {
  const qc = useQueryClient();
  const [liveStep, setLiveStep] = useState<string | null>(null);
  const [tab, setTab] = useState("overview");
  const [period, setPeriod] = useState<"1M" | "3M" | "YTD" | "1Y" | "ALL">("ALL");

  const backtest = useQuery({
    queryKey: ["backtest", backtestId],
    queryFn: () => api.getBacktest(backtestId),
    refetchInterval: (q) =>
      q.state.data && ["QUEUED", "STARTING", "RUNNING"].includes(q.state.data.status)
        ? 1500
        : false,
  });

  const cancel = useMutation({
    mutationFn: () => api.cancelBacktest(backtestId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["backtest", backtestId] });
      qc.invalidateQueries({ queryKey: ["backtests"] });
      toast("已取消回测", "info");
    },
  });

  useEffect(() => {
    if (!backtest.data) return;
    if (!["QUEUED", "STARTING", "RUNNING"].includes(backtest.data.status)) return;
    const es = new EventSource(api.eventsUrl(backtestId));
    es.addEventListener("progress", (ev) => {
      try {
        const payload = JSON.parse((ev as MessageEvent).data);
        setLiveStep(payload.progress_step || payload.status);
      } catch {
        /* ignore */
      }
    });
    es.addEventListener("done", () => {
      es.close();
      backtest.refetch();
    });
    return () => es.close();
  }, [backtest.data?.status, backtestId]); // eslint-disable-line react-hooks/exhaustive-deps

  const ready = backtest.data?.status === "COMPLETED";
  const metrics = useQuery({
    queryKey: ["metrics", backtestId],
    queryFn: () => api.getMetrics(backtestId),
    enabled: ready,
  });
  const equity = useQuery({
    queryKey: ["equity", backtestId],
    queryFn: () => api.getEquity(backtestId),
    enabled: ready,
  });
  const trades = useQuery({
    queryKey: ["trades", backtestId],
    queryFn: () => api.getTrades(backtestId),
    enabled: ready,
  });
  const monthly = useQuery({
    queryKey: ["monthly", backtestId],
    queryFn: () => api.getMonthlyReturns(backtestId),
    enabled: ready,
  });

  const equityPoints = useMemo(() => {
    const raw = (equity.data || []).map((p) => ({
      time: p.ts,
      strategy: p.strategy_value,
      benchmark: p.benchmark_value,
    }));
    return filterEquityByPeriod(raw, period);
  }, [equity.data, period]);
  const drawdownPoints = useMemo(
    () => (equity.data || []).map((p) => ({ time: p.ts, value: p.drawdown ?? 0 })),
    [equity.data],
  );

  if (backtest.isLoading || !backtest.data) {
    return <Card className="h-80 animate-pulse bg-as-secondary" />;
  }

  const bt = backtest.data;
  const m = metrics.data;
  const running = ["QUEUED", "STARTING", "RUNNING"].includes(bt.status);
  const currentStep = labelStep(liveStep || bt.progress_step);

  function exportTrades() {
    const rows = trades.data || [];
    const header = ["日期", "标的", "方向", "数量", "价格", "佣金"];
    const csv = [
      header.join(","),
      ...rows.map((t) =>
        [
          t.trade_date.slice(0, 10),
          t.ticker,
          labelDirection(t.direction, t.quantity),
          t.quantity,
          t.entry_price ?? "",
          t.commission ?? "",
        ].join(","),
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `backtest-${backtestId.slice(0, 8)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast("已导出成交明细", "ok");
  }

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        crumbs={[
          { href: "/", label: "首页" },
          { href: "/backtests", label: "回测" },
        ]}
        title={bt.strategy_name || "回测工作室"}
        description={`${bt.start_date} — ${bt.end_date} · 日线 · 基准 ${bt.benchmark}${
          bt.version_number ? ` · v${bt.version_number}` : ""
        }`}
        action={
          <div className="flex items-center gap-2">
            <Badge
              tone={
                bt.status === "COMPLETED" ? "green" : bt.status === "FAILED" ? "red" : "blue"
              }
            >
              {labelStatus(bt.status)}
            </Badge>
            {bt.strategy_id ? (
              <Link href={`/strategies/${bt.strategy_id}`}>
                <Button variant="secondary" size="sm">
                  打开策略
                </Button>
              </Link>
            ) : null}
            {running ? (
              <Button
                variant="danger"
                size="sm"
                onClick={() => cancel.mutate()}
                disabled={cancel.isPending}
              >
                {cancel.isPending ? "取消中…" : "取消回测"}
              </Button>
            ) : null}
          </div>
        }
      />

      {!ready ? (
        <Card className="min-h-[320px]">
          {running ? (
            <div className="flex min-h-[280px] flex-col items-center justify-center gap-6 px-6">
              <ProgressSteps steps={RUN_STEPS} current={currentStep || "排队中"} />
              <p className="text-sm text-as-muted">{currentStep || "正在准备 LEAN 环境"}</p>
            </div>
          ) : (
            <EmptyState
              icon={LineChart}
              title={bt.status === "FAILED" ? "回测失败" : "回测已取消"}
              description={
                bt.status === "FAILED"
                  ? bt.error?.message || "请查看 Worker / API 日志。"
                  : "可以回到策略实验室重新运行。"
              }
              action={
                bt.strategy_id ? (
                  <Link href={`/strategies/${bt.strategy_id}`}>
                    <Button size="sm">返回策略</Button>
                  </Link>
                ) : null
              }
            />
          )}
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6 as-stagger">
            <MetricTile
              label="Deflated Sharpe"
              value={m?.deflated_sharpe == null ? "—" : formatPct(m.deflated_sharpe as number)}
              hint={
                m?.dsr_n_trials != null
                  ? `N=${m.dsr_n_trials} 次试验 · 阈值 95%`
                  : "来自试验台账的多重检验修正"
              }
              tone={
                typeof m?.deflated_sharpe === "number"
                  ? m.deflated_sharpe >= 0.95
                    ? "pos"
                    : "neg"
                  : undefined
              }
            />
            <MetricTile label="总收益" value={formatPct(m?.total_return)} tone={metricTone(m?.total_return)} />
            <MetricTile label="年化 CAGR" value={formatPct(m?.cagr)} tone={metricTone(m?.cagr)} />
            <MetricTile label="夏普" value={formatNumber(m?.sharpe)} />
            <MetricTile label="索提诺" value={formatNumber(m?.sortino)} />
            <MetricTile label="最大回撤" value={formatPct(m?.max_drawdown)} tone="neg" />
            <MetricTile label="波动率" value={formatPct(m?.volatility)} />
            <MetricTile label="超额收益" value={formatPct(m?.excess_return)} tone={metricTone(m?.excess_return)} />
            <MetricTile label="CAPM α" value={formatPct(m?.alpha_capm)} tone={metricTone(m?.alpha_capm)} />
            <MetricTile label="β" value={formatNumber(m?.beta)} />
            <MetricTile label="信息比率" value={formatNumber(m?.information_ratio)} />
            <MetricTile label="卡尔玛" value={formatNumber(m?.calmar)} />
            <MetricTile label="基准收益" value={formatPct(m?.benchmark_return)} tone={metricTone(m?.benchmark_return)} />
            <MetricTile label="成交笔数" value={formatNumber(m?.trade_count, 0)} />
            <MetricTile label="期末权益" value={formatUsd(m?.final_equity)} />
            <MetricTile label="佣金" value={formatUsd(m?.commission, 2)} />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <Tabs
              value={tab}
              onChange={setTab}
              items={[
                { id: "overview", label: "概览" },
                { id: "trades", label: "成交" },
                { id: "monthly", label: "月度" },
              ]}
            />
            <div className="flex items-center gap-2 text-xs text-as-muted">
              <button
                type="button"
                className="inline-flex cursor-pointer items-center gap-1 rounded-lg px-2 py-1 hover:bg-as-secondary hover:text-as-text"
                onClick={() => {
                  navigator.clipboard.writeText(bt.data_version || "");
                  toast("已复制数据指纹", "ok");
                }}
              >
                <Copy className="h-3 w-3" />
                数据 {bt.data_version ? `${bt.data_version.slice(0, 12)}…` : "—"}
              </button>
              <span>引擎 {bt.engine_version || "—"}</span>
              <Button variant="secondary" size="sm" onClick={exportTrades}>
                <Download className="h-3.5 w-3.5" />
                导出 CSV
              </Button>
            </div>
          </div>

          {tab === "overview" ? (
            <div className="space-y-4">
              <Card>
                <CardHeader
                  title="权益曲线"
                  hint={<span className="text-[11px] text-as-muted">策略 vs 基准</span>}
                  action={
                    <Tabs
                      value={period}
                      onChange={(id) => setPeriod(id as typeof period)}
                      items={[
                        { id: "1M", label: "1月" },
                        { id: "3M", label: "3月" },
                        { id: "YTD", label: "今年" },
                        { id: "1Y", label: "1年" },
                        { id: "ALL", label: "全部" },
                      ]}
                    />
                  }
                />
                <EquityCurve data={equityPoints} />
              </Card>
              <Card>
                <CardHeader title="回撤" />
                <DrawdownChart data={drawdownPoints} />
              </Card>
            </div>
          ) : null}

          {tab === "monthly" ? (
            <Card>
              <CardHeader title="月度收益" />
              <MonthlyHeatmap data={monthly.data || []} />
            </Card>
          ) : null}

          {tab === "trades" ? (
            <Card className="overflow-hidden p-0">
              <div className="border-b border-as-border px-5 py-4 text-sm font-medium">成交明细</div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[900px] text-left text-xs">
                  <thead className="sticky top-0 bg-as-secondary/90 text-as-muted backdrop-blur-sm">
                    <tr>
                      {["日期", "标的", "方向", "数量", "价格", "佣金"].map((h) => (
                        <th key={h} className="px-4 py-3 font-medium">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(trades.data || []).slice(0, 200).map((t) => {
                      const dir = labelDirection(t.direction, t.quantity);
                      const sell = dir === "卖出";
                      return (
                      <tr key={t.id} className="border-t border-as-border/70 hover:bg-as-secondary/50">
                        <td className="px-4 py-2.5 tabular">{t.trade_date.slice(0, 10)}</td>
                        <td className="px-4 py-2.5">{t.ticker}</td>
                        <td className={`px-4 py-2.5 ${sell ? "text-as-negative" : "text-as-positive"}`}>
                          {dir}
                        </td>
                        <td className="px-4 py-2.5 tabular">{formatNumber(t.quantity, 0)}</td>
                        <td className="px-4 py-2.5 tabular">{formatNumber(t.entry_price)}</td>
                        <td className="px-4 py-2.5 tabular">{formatNumber(t.commission)}</td>
                      </tr>
                      );
                    })}
                    {!trades.data?.length ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-8 text-center text-as-muted">
                          暂无成交记录。
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </Card>
          ) : null}
        </>
      )}
    </div>
  );
}
