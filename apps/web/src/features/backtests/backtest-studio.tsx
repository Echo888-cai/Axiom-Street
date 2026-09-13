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
import { useT } from "@/lib/i18n";
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

export function BacktestStudio({ backtestId }: { backtestId: string }) {
  const t = useT();
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
      toast(t("backtest.toast.cancelled"), "info");
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
          title={t("backtest.states.readError")}
          description={backtest.error.message}
          action={
            <Button variant="secondary" onClick={() => backtest.refetch()}>
              {t("backtest.action.reload")}
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
  const runSteps = [
    t("backtest.steps.queued"),
    t("backtest.steps.preparing"),
    t("backtest.steps.loading"),
    t("backtest.steps.running"),
    t("backtest.steps.computing"),
  ];

  function exportTrades() {
    const rows = trades.data || [];
    const header = [
      t("backtest.tradeColumns.date"),
      t("backtest.tradeColumns.ticker"),
      t("backtest.tradeColumns.direction"),
      t("backtest.tradeColumns.quantity"),
      t("backtest.tradeColumns.entry"),
      t("backtest.tradeColumns.exit"),
      t("backtest.tradeColumns.pnl"),
      t("backtest.tradeColumns.holdingPeriod"),
      t("backtest.tradeColumns.commission"),
    ];
    const csv = [
      header.join(","),
      ...rows.map((tr) =>
        [
          tr.trade_date.slice(0, 10),
          tr.ticker,
          labelDirection(tr.direction, tr.quantity),
          tr.quantity,
          tr.entry_price ?? "",
          tr.exit_price ?? "",
          tr.pnl ?? "",
          tr.holding_period ?? "",
          tr.commission ?? "",
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
    toast(t("backtest.toast.exported"), "ok");
  }

  const noteHref =
    bt.strategy_id != null
      ? `/reports?strategy_id=${bt.strategy_id}&backtest_id=${bt.id}`
      : "/reports";

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        crumbs={[
          { href: "/", label: t("backtest.crumbs.home") },
          { href: "/backtests", label: t("backtest.title") },
        ]}
        title={bt.strategy_name || "Tearsheet"}
        description={`${bt.start_date} — ${bt.end_date} · ${bt.benchmark}${
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
                  {t("backtest.action.openStrategy")}
                </Button>
              </Link>
            ) : null}
            <Link href={noteHref}>
              <Button variant="secondary" size="sm">
                <NotebookPen className="h-3.5 w-3.5" />
                {t("backtest.action.writeNote")}
              </Button>
            </Link>
            {running ? (
              <Button
                variant="danger"
                size="sm"
                onClick={() => cancel.mutate()}
                disabled={cancel.isPending}
              >
                {cancel.isPending ? t("backtest.action.cancelling") : t("backtest.action.cancelBacktest")}
              </Button>
            ) : null}
          </div>
        }
      />

      {!ready ? (
        <Card className="min-h-[320px]">
          {running ? (
            <div className="flex min-h-[280px] flex-col items-center justify-center gap-6 px-6">
              <ProgressSteps steps={runSteps} current={currentStep || t("backtest.steps.queued")} />
              <p className="text-sm text-as-muted">
                {currentStep || t("backtest.states.preparingEnv")}
              </p>
            </div>
          ) : (
            <EmptyState
              icon={LineChart}
              title={bt.status === "FAILED" ? t("backtest.states.failed") : t("backtest.states.cancelled")}
              description={
                bt.status === "FAILED"
                  ? bt.error?.message || t("backtest.states.failedLogHint")
                  : t("backtest.states.cancelledHint")
              }
              action={
                bt.strategy_id ? (
                  <Link href={`/strategies/${bt.strategy_id}`}>
                    <Button size="sm">{t("backtest.action.backToStrategy")}</Button>
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
              <CardHeader title={t("backtest.states.monthlyTitle")} />
              <MonthlyHeatmap data={monthly.data || []} />
            </Card>
          ) : null}

          {tab === "trades" ? <TradesTable rows={trades.data || []} /> : null}
        </>
      )}
    </div>
  );
}
