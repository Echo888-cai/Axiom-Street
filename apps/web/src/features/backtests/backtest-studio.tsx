"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Copy, Download, LineChart, NotebookPen } from "lucide-react";
import { api, type Backtest } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { EquityCurve, type EquityMarker, type EquitySeries } from "@/components/charts/equity-curve";
import { DrawdownChart } from "@/components/charts/drawdown-chart";
import { MonthlyHeatmap } from "@/components/charts/monthly-heatmap";
import { formatNumber, formatPct, formatUsd, filterEquityByPeriod, cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs } from "@/components/ui/tabs";
import { ProgressSteps } from "@/components/ui/progress-steps";
import { MetricTile, metricTone } from "@/components/ui/metric-tile";
import { toast } from "@/components/ui/toast";
import { labelDirection, labelStatus, labelStep } from "@/lib/labels";
import { TruthStrip } from "@/features/tearsheet/truth-strip";
import { DistributionPanel } from "@/features/tearsheet/distribution-panel";
import { RollingPanel } from "@/features/tearsheet/rolling-panel";
import { ExposurePanel } from "@/features/tearsheet/exposure-panel";
import type { ExposurePoint } from "@/components/charts/exposure-chart";
import {
  dailyReturnsFromEquity,
  histogram,
  normalizeSeries,
  pairedDailyReturns,
  qqNormal,
  rollingBeta,
  rollingSharpe,
} from "@/lib/tearsheet";

const RUN_STEPS = ["排队中", "准备环境", "加载数据", "运行策略", "计算指标"];

function Toggle({
  pressed,
  onPressed,
  children,
  disabled,
}: {
  pressed: boolean;
  onPressed: () => void;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onPressed}
      className={cn(
        "h-8 rounded-lg px-2.5 text-[11px] font-medium outline-none transition-colors duration-as",
        "focus-visible:ring-2 focus-visible:ring-as-primary/30",
        pressed ? "bg-as-bg text-as-text shadow-sm" : "text-as-muted hover:text-as-text",
        disabled && "cursor-not-allowed opacity-40",
      )}
    >
      {children}
    </button>
  );
}

export function BacktestStudio({ backtestId }: { backtestId: string }) {
  const qc = useQueryClient();
  const [liveStep, setLiveStep] = useState<string | null>(null);
  const [tab, setTab] = useState("curve");
  const [period, setPeriod] = useState<"1M" | "3M" | "YTD" | "1Y" | "ALL">("ALL");
  const [logScale, setLogScale] = useState(false);
  const [normalized, setNormalized] = useState(false);
  const [showTrades, setShowTrades] = useState(false);
  const [compareId, setCompareId] = useState("");

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
        /* EventSource payload may be a heartbeat without JSON */
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
  const timeSeries = useQuery({
    queryKey: ["time-series", backtestId],
    queryFn: () => api.getTimeSeries(backtestId),
    enabled: ready,
  });
  const pboQuery = useQuery({
    queryKey: ["validation", backtest.data?.strategy_id, "PBO"],
    queryFn: () => api.listValidation({ strategy_id: backtest.data?.strategy_id || "", kind: "PBO" }),
    enabled: ready && Boolean(backtest.data?.strategy_id),
  });
  const peers = useQuery({
    queryKey: ["backtests", backtest.data?.strategy_id, "COMPLETED"],
    queryFn: () =>
      api.listBacktests({ strategy_id: backtest.data?.strategy_id || "", status: "COMPLETED" }),
    enabled: Boolean(backtest.data?.strategy_id),
  });
  const compareEquity = useQuery({
    queryKey: ["equity", compareId],
    queryFn: () => api.getEquity(compareId),
    enabled: Boolean(compareId),
  });

  const pbo = useMemo(() => {
    const items = pboQuery.data?.items || [];
    const latest = items.find((row) => row.status === "COMPLETED" && !row.error);
    const value = latest?.result?.pbo;
    return typeof value === "number" ? value : null;
  }, [pboQuery.data]);

  const filteredEquity = useMemo(() => {
    const raw = (equity.data || []).map((p) => ({
      time: p.ts,
      strategy: p.strategy_value,
      benchmark: p.benchmark_value,
      drawdown: p.drawdown,
    }));
    return filterEquityByPeriod(raw, period);
  }, [equity.data, period]);

  const distribution = useMemo(() => {
    const values = (equity.data || []).map((p) => p.strategy_value);
    const benches = (equity.data || []).map((p) => p.benchmark_value);
    const times = (equity.data || []).slice(1).map((p) => p.ts);
    const daily = dailyReturnsFromEquity(values);
    if (daily.error) {
      return {
        error: daily.error,
        bins: [],
        qq: [],
        rolling: { points: [], error: daily.error },
        beta: { points: [], error: daily.error },
      };
    }
    const hist = histogram(daily.returns);
    const qq = qqNormal(daily.returns);
    const rolling = rollingSharpe(daily.returns, times);
    const paired = pairedDailyReturns(values, benches, times);
    const beta = paired.error
      ? { points: [], error: paired.error }
      : rollingBeta(paired.strategy, paired.benchmark, paired.times);
    return {
      error: hist.error || qq.error,
      bins: hist.bins,
      qq: qq.points,
      rolling,
      beta,
    };
  }, [equity.data]);

  const exposure = useMemo(() => {
    const rows = timeSeries.data || [];
    const byTime = new Map<string, ExposurePoint>();
    const turnover: { time: string; value: number }[] = [];
    for (const row of rows) {
      const time = row.ts;
      if (row.name === "turnover") {
        turnover.push({ time, value: row.value });
        continue;
      }
      const current = byTime.get(time) || { time };
      if (row.name === "exposure_long") current.long = row.value;
      if (row.name === "exposure_short") current.short = row.value;
      byTime.set(time, current);
    }
    const points = [...byTime.values()]
      .map((p) => ({
        ...p,
        net: p.long != null || p.short != null ? (p.long || 0) - (p.short || 0) : undefined,
      }))
      .sort((a, b) => a.time.localeCompare(b.time));
    return { points, turnover };
  }, [timeSeries.data]);

  const canLog = filteredEquity.every((p) => p.strategy > 0);
  const series: EquitySeries[] = useMemo(() => {
    const strategyValues = filteredEquity.map((p) => p.strategy);
    const benchValues = filteredEquity.map((p) => p.benchmark);
    const strategyNorm = normalized ? normalizeSeries(strategyValues) : { values: strategyValues };
    const out: EquitySeries[] = [
      {
        id: "strategy",
        label: normalized ? "本回测（=100）" : "本回测",
        color: "#1677FF",
        data: filteredEquity.map((p, i) => ({
          time: p.time,
          value: strategyNorm.values[i] ?? p.strategy,
        })),
      },
    ];
    if (!normalized) {
      const benchPoints = filteredEquity
        .map((p) => (p.benchmark != null ? { time: p.time, value: p.benchmark } : null))
        .filter((p): p is { time: string; value: number } => p != null);
      if (benchPoints.length) {
        out.push({ id: "benchmark", label: "基准", color: "#98A2B3", dashed: true, data: benchPoints });
      }
    } else {
      const aligned = benchValues
        .map((v, i) => (v != null && v > 0 ? { time: filteredEquity[i].time, value: v } : null))
        .filter((p): p is { time: string; value: number } => p != null);
      if (aligned.length) {
        const norm = normalizeSeries(aligned.map((p) => p.value));
        if (!norm.error) {
          out.push({
            id: "benchmark",
            label: "基准（=100）",
            color: "#98A2B3",
            dashed: true,
            data: aligned.map((p, i) => ({ time: p.time, value: norm.values[i] })),
          });
        }
      }
    }
    if (compareId && compareEquity.data?.length) {
      const compareRaw = filterEquityByPeriod(
        compareEquity.data.map((p) => ({ time: p.ts, strategy: p.strategy_value })),
        period,
      );
      const source = compareRaw.map((p) => p.strategy);
      const scaled = normalized ? normalizeSeries(source) : { values: source };
      if (!scaled.error) {
        const peer = (peers.data || []).find((row) => row.id === compareId);
        out.push({
          id: "compare",
          label: peerLabel(peer, normalized),
          color: "#12B76A",
          dashed: true,
          data: compareRaw.map((p, i) => ({ time: p.time, value: scaled.values[i] })),
        });
      }
    }
    return out;
  }, [compareEquity.data, compareId, filteredEquity, normalized, peers.data, period]);

  const markers: EquityMarker[] = useMemo(() => {
    if (!showTrades) return [];
    return (trades.data || []).map((t) => {
      const buy = labelDirection(t.direction, t.quantity) !== "卖出";
      return {
        time: t.trade_date,
        label: t.ticker,
        buy,
      };
    });
  }, [showTrades, trades.data]);

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
    const header = ["日期", "标的", "方向", "数量", "入场价", "出场价", "盈亏", "持有期", "佣金"];
    const csv = [
      header.join(","),
      ...rows.map((t) =>
        [
          t.trade_date.slice(0, 10),
          t.ticker,
          labelDirection(t.direction, t.quantity),
          t.quantity,
          t.entry_price ?? "",
          t.exit_price ?? "",
          t.pnl ?? "",
          t.holding_period ?? "",
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

  const noteHref =
    bt.strategy_id != null
      ? `/reports?strategy_id=${bt.strategy_id}&backtest_id=${bt.id}`
      : "/reports";

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        crumbs={[
          { href: "/", label: "首页" },
          { href: "/backtests", label: "回测" },
        ]}
        title={bt.strategy_name || "Tearsheet"}
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
            <Link href={noteHref}>
              <Button variant="secondary" size="sm">
                <NotebookPen className="h-3.5 w-3.5" />
                写研究笔记
              </Button>
            </Link>
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
          <TruthStrip metrics={m} pbo={pbo} strategyId={bt.strategy_id} />

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6 as-stagger">
            <MetricTile label="总收益" value={formatPct(m?.total_return)} tone={metricTone(m?.total_return)} />
            <MetricTile label="年化 CAGR" value={formatPct(m?.cagr)} tone={metricTone(m?.cagr)} />
            <MetricTile label="最大回撤" value={formatPct(m?.max_drawdown)} tone="neg" />
            <MetricTile label="波动率" value={formatPct(m?.volatility)} />
            <MetricTile label="超额收益" value={formatPct(m?.excess_return)} tone={metricTone(m?.excess_return)} />
            <MetricTile label="CAPM α" value={formatPct(m?.alpha_capm)} tone={metricTone(m?.alpha_capm)} />
            <MetricTile label="β" value={formatNumber(m?.beta)} />
            <MetricTile label="信息比率" value={formatNumber(m?.information_ratio)} />
            <MetricTile label="索提诺" value={formatNumber(m?.sortino)} />
            <MetricTile label="卡尔玛" value={formatNumber(m?.calmar)} />
            <MetricTile label="成交笔数" value={formatNumber(m?.trade_count, 0)} />
            <MetricTile label="期末权益" value={formatUsd(m?.final_equity)} />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <Tabs
              value={tab}
              onChange={setTab}
              items={[
                { id: "curve", label: "曲线" },
                { id: "distribution", label: "分布" },
                { id: "rolling", label: "滚动" },
                { id: "exposure", label: "暴露" },
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
              <a href={api.tearsheetPdfUrl(backtestId)} target="_blank" rel="noreferrer">
                <Button variant="secondary" size="sm">
                  <Download className="h-3.5 w-3.5" />
                  PDF
                </Button>
              </a>
              <a href={api.tearsheetHtmlUrl(backtestId)} target="_blank" rel="noreferrer">
                <Button variant="ghost" size="sm">
                  HTML
                </Button>
              </a>
            </div>
          </div>

          {tab === "curve" ? (
            <div className="space-y-4">
              <Card>
                <CardHeader
                  title="权益曲线"
                  hint={
                    <span className="text-[11px] text-as-muted">
                      {normalized ? "各序列独立归一到 100，才能叠在一起看" : "绝对净值"}
                    </span>
                  }
                  action={
                    <div className="flex flex-wrap items-center justify-end gap-2">
                      <div className="inline-flex rounded-xl bg-as-secondary p-1">
                        <Toggle pressed={logScale} disabled={!canLog} onPressed={() => setLogScale((v) => !v)}>
                          对数
                        </Toggle>
                        <Toggle pressed={normalized} onPressed={() => setNormalized((v) => !v)}>
                          归一到 100
                        </Toggle>
                        <Toggle pressed={showTrades} onPressed={() => setShowTrades((v) => !v)}>
                          成交标记
                        </Toggle>
                      </div>
                      <label className="flex items-center gap-1.5 text-[11px] text-as-muted">
                        对比
                        <select
                          className="h-8 max-w-[220px] rounded-lg border border-as-border bg-as-bg px-2 text-xs text-as-text outline-none focus:border-as-primary/40"
                          value={compareId}
                          onChange={(e) => setCompareId(e.target.value)}
                        >
                          <option value="">不叠加</option>
                          {(peers.data || [])
                            .filter((row) => row.id !== backtestId)
                            .map((row) => (
                              <option key={row.id} value={row.id}>
                                {peerLabel(row, false)}
                              </option>
                            ))}
                        </select>
                      </label>
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
                    </div>
                  }
                />
                {!canLog && logScale ? (
                  <p className="mb-3 text-xs text-as-negative">权益含非正值，对数坐标不可用。</p>
                ) : null}
                <EquityCurve
                  series={series}
                  logScale={logScale && canLog}
                  markers={markers}
                  height={340}
                />
              </Card>
              <Card>
                <CardHeader title="回撤" />
                <DrawdownChart data={drawdownPoints} />
              </Card>
            </div>
          ) : null}

          {tab === "distribution" ? (
            <DistributionPanel
              metrics={m}
              bins={distribution.bins}
              qq={distribution.qq}
              error={distribution.error}
            />
          ) : null}

          {tab === "rolling" ? (
            <RollingPanel
              sharpe={distribution.rolling.points}
              sharpeError={distribution.rolling.error}
              beta={distribution.beta.points}
              betaError={distribution.beta.error}
            />
          ) : null}

          {tab === "exposure" ? (
            <ExposurePanel
              points={exposure.points}
              turnover={exposure.turnover}
              gross={m?.gross_exposure}
              net={m?.net_exposure}
            />
          ) : null}

          {tab === "monthly" ? (
            <Card>
              <CardHeader title="月度收益" />
              <MonthlyHeatmap data={monthly.data || []} />
            </Card>
          ) : null}

          {tab === "trades" ? (
            <Card className="overflow-hidden p-0">
              <div className="border-b border-as-border px-5 py-4">
                <div className="text-sm font-medium">成交明细</div>
                <p className="mt-1 text-[11px] text-as-muted">
                  出场价、盈亏、持有期目前为空——引擎还没有 round-trip 配对，这里不填假数。
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[980px] text-left text-xs">
                  <thead className="sticky top-0 bg-as-secondary/90 text-as-muted backdrop-blur-sm">
                    <tr>
                      {["日期", "标的", "方向", "数量", "入场价", "出场价", "盈亏", "持有期", "佣金"].map((h) => (
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
                          <td className="px-4 py-2.5 tabular">{formatNumber(t.exit_price)}</td>
                          <td className="px-4 py-2.5 tabular">{formatNumber(t.pnl)}</td>
                          <td className="px-4 py-2.5 tabular">{formatNumber(t.holding_period, 0)}</td>
                          <td className="px-4 py-2.5 tabular">{formatNumber(t.commission)}</td>
                        </tr>
                      );
                    })}
                    {!trades.data?.length ? (
                      <tr>
                        <td colSpan={9} className="px-4 py-8 text-center text-as-muted">
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

function peerLabel(row: Backtest | undefined, normalized: boolean): string {
  if (!row) return normalized ? "对比（=100）" : "对比";
  const range = `${row.start_date.slice(0, 10)} → ${row.end_date.slice(0, 10)}`;
  const version = row.version_number ? `v${row.version_number}` : row.id.slice(0, 8);
  return normalized ? `${version} ${range}（=100）` : `${version} ${range}`;
}
