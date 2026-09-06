"use client";
import { useBacktestAnalysis } from "./use-backtest-analysis";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { LineChart, NotebookPen } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { ProgressSteps } from "@/components/ui/progress-steps";
import { MonthlyHeatmap } from "@/components/charts/monthly-heatmap";
import { toast } from "@/components/ui/toast";
import { labelStatus, labelStep, labelDirection } from "@/lib/labels";
import { TruthStrip } from "@/features/tearsheet/truth-strip";
import { DistributionPanel } from "@/features/tearsheet/distribution-panel";
import { RollingPanel } from "@/features/tearsheet/rolling-panel";
import { ExposurePanel } from "@/features/tearsheet/exposure-panel";
import { MetricStrip } from "./metric-strip";
import { StudioTopBar, type StudioTab } from "./studio-top-bar";
import { CurveCard } from "./curve-card";
import { TradesTable } from "./trades-table";
import { ComparePanel } from "./compare-panel";
import { MaeMfePanel } from "./mae-mfe-panel";

const RUN_STEPS = ["排队中", "准备环境", "加载数据", "运行策略", "计算指标"];

export function BacktestStudio({ backtestId }: { backtestId: string }) {
  const qc = useQueryClient();
  const [liveStep, setLiveStep] = useState<string | null>(null);
  const [tab, setTab] = useState<StudioTab>("curve");
  const [period, setPeriod] = useState<"1M" | "3M" | "YTD" | "1Y" | "ALL">("ALL");
  const [logScale, setLogScale] = useState(false);
  const [normalized, setNormalized] = useState(false);
  const [showTrades, setShowTrades] = useState(false);
  const [compareId, setCompareId] = useState("");

  const backtest = useQuery({
    queryKey: ["backtest", backtestId],
    queryFn: () => api.getBacktest(backtestId),
    refetchInterval: (q) =>
      q.state.data &&
      ["QUEUED", "STARTING", "RUNNING"].includes(q.state.data.status)
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

  const {
    metrics,
    trades,
    monthly,
    peers,
    pbo,
    distribution,
    exposure,
    canLog,
    series,
    markers,
    drawdownPoints,
  } = useBacktestAnalysis({
    backtest: backtest.data,
    backtestId,
    compareId,
    period,
    normalized,
    showTrades,
  });

  if (backtest.isError)
    return (
      <Card>
        <EmptyState
          title="无法读取这次回测"
          description={backtest.error.message}
          action={
            <Button variant="secondary" onClick={() => backtest.refetch()}>
              重新读取
            </Button>
          }
        />
      </Card>
    );

  if (backtest.isLoading || !backtest.data) {
    return <Card className="h-80 animate-pulse bg-as-secondary" />;
  }

  const ready = backtest.data?.status === "COMPLETED";
  const bt = backtest.data;
  const m = metrics.data;
  const running = ["QUEUED", "STARTING", "RUNNING"].includes(bt.status);
  const currentStep = labelStep(liveStep || bt.progress_step);

  function exportTrades() {
    const rows = trades.data || [];
    const header = [
      "日期", "标的", "方向", "数量", "入场价", "出场价", "盈亏", "持有期", "佣金",
    ];
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
                bt.status === "COMPLETED"
                  ? "green"
                  : bt.status === "FAILED"
                    ? "red"
                    : "blue"
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
              <p className="text-sm text-as-muted">
                {currentStep || "正在准备 LEAN 环境"}
              </p>
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
          <MetricStrip m={m} />
          <StudioTopBar
            backtestId={backtestId}
            dataVersion={bt.data_version}
            engineVersion={bt.engine_version}
            tab={tab}
            onTabChange={setTab}
            onExport={exportTrades}
          />

          {tab === "curve" ? (
            <CurveCard
              backtestId={backtestId}
              series={series}
              markers={markers}
              drawdownPoints={drawdownPoints}
              peers={peers.data || []}
              canLog={canLog}
              logScale={logScale}
              onLogScale={setLogScale}
              normalized={normalized}
              onNormalized={setNormalized}
              showTrades={showTrades}
              onShowTrades={setShowTrades}
              compareId={compareId}
              onCompareId={setCompareId}
              period={period}
              onPeriod={setPeriod}
            />
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

          {tab === "compare" ? <ComparePanel currentBacktestId={backtestId} /> : null}
          {tab === "mae-mfe" ? <MaeMfePanel backtestId={backtestId} /> : null}

          {tab === "monthly" ? (
            <Card>
              <CardHeader title="月度收益" />
              <MonthlyHeatmap data={monthly.data || []} />
            </Card>
          ) : null}

          {tab === "trades" ? <TradesTable rows={trades.data || []} /> : null}
        </>
      )}
    </div>
  );
}
