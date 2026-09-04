import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChevronLeft, Download, PanelRight, RotateCcw } from "lucide-react";
import { cn } from "@/lib/cn";
import { fmtCurrency, fmtDate, fmtDuration, fmtPct } from "@/lib/format";
import { useApp } from "@/store/app";
import { getStrategy, getVersion } from "@/mocks/strategies";
import { backtestsFor, getVersionData, rebase } from "@/mocks/engine";
import type { SeriesPoint, Trade } from "@/mocks/types";
import {
  ContextActions,
  ContextBar,
  ContextDivider,
  HonestyMarker,
} from "@/components/shell/context-bar";
import { Button, IconButton } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { MetricCell, MetricStrip } from "@/components/ui/metric";
import { DataTable, type Column } from "@/components/ui/data-table";
import { RunBadge, Tag } from "@/components/ui/badge";
import { LineChart, COLORS } from "@/components/charts/line-chart";
import { MonthlyHeatmap } from "@/components/charts/monthly-heatmap";
import { TradeDistribution } from "@/components/charts/trade-distribution";

type ChartMode = "Equity" | "Drawdown" | "Benchmark" | "Exposure";
const MODES: ChartMode[] = ["Equity", "Drawdown", "Benchmark", "Exposure"];

export function BacktestDetailPage() {
  const { id = "bt-strat-momentum-alpha-184" } = useParams();
  const navigate = useNavigate();
  const { pushToast, toggleCopilot } = useApp();
  const [mode, setMode] = useState<ChartMode>("Equity");

  // Resolve run → strategy → version
  const strategyId = id.startsWith("bt-") ? id.slice(3, id.lastIndexOf("-")) : "strat-momentum-alpha";
  const strategy = getStrategy(strategyId);
  const run = useMemo(
    () => backtestsFor(strategy).find((b) => b.id === id) ?? backtestsFor(strategy)[0],
    [strategy, id],
  );
  const v = getVersion(strategy, run.version);
  const data = getVersionData(v);
  const m = data.metrics;

  const chartNode = useMemo(() => {
    if (mode === "Drawdown") {
      return (
        <LineChart
          baseline
          series={[
            { data: data.drawdown, color: COLORS.neg, area: true, lineWidth: 1 },
            { data: data.benchmarkDrawdown, color: COLORS.bench, lineWidth: 1, dashed: true },
          ]}
        />
      );
    }
    if (mode === "Benchmark") {
      return (
        <LineChart
          series={[
            { data: rebase(data.benchmark), color: COLORS.bench, area: true, lineWidth: 2 },
            { data: rebase(data.equity), color: COLORS.accent, lineWidth: 1, dashed: true },
          ]}
        />
      );
    }
    if (mode === "Exposure") {
      return (
        <LineChart
          series={[{ data: data.exposure, color: COLORS.info, area: true, lineWidth: 1 }]}
        />
      );
    }
    return (
      <LineChart
        series={[
          { data: rebase(data.equity), color: COLORS.accent, area: true, lineWidth: 2 },
          { data: rebase(data.benchmark), color: COLORS.bench, lineWidth: 1, dashed: true },
        ]}
      />
    );
  }, [mode, data]);

  const ddPeriods = useMemo(() => drawdownPeriods(data.drawdown), [data.drawdown]);

  const tradeCols: Column<Trade>[] = [
    { key: "id", header: "ID", mono: true, render: (t) => <span className="text-text-3">{t.id}</span> },
    { key: "sym", header: "Symbol", mono: true, render: (t) => <span className="text-text">{t.symbol}</span> },
    { key: "side", header: "Side", render: (t) => <span className={cn("mono text-[11px]", t.side === "LONG" ? "text-pos" : "text-neg")}>{t.side}</span> },
    { key: "xd", header: "Exit", mono: true, render: (t) => fmtDate(t.exitDate) },
    { key: "hold", header: "Days", align: "right", mono: true, render: (t) => t.holdingDays },
    { key: "pnl", header: "P&L", align: "right", mono: true, render: (t) => <span className={t.pnl >= 0 ? "text-pos" : "text-neg"}>{fmtCurrency(t.pnl, 0, true)}</span> },
    { key: "pct", header: "Return", align: "right", mono: true, render: (t) => <span className={t.pnlPct >= 0 ? "text-pos" : "text-neg"}>{fmtPct(t.pnlPct)}</span> },
  ];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ContextBar>
        <button
          onClick={() => navigate("/backtests")}
          className="interactive flex h-6.5 w-6.5 shrink-0 cursor-pointer items-center justify-center rounded-md text-text-3 hover:bg-raised hover:text-text"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate text-[13.5px] font-semibold text-text">{strategy.name}</span>
          <span className="text-text-4">/</span>
          <span className="mono text-[13px] text-text-2">Backtest #{run.run}</span>
          <RunBadge status={run.status} />
          <Tag>{v.version}</Tag>
        </div>
        <ContextDivider />
        <div className="mono hidden shrink-0 items-center gap-3 text-[10.5px] text-text-3 xl:flex">
          <span>{fmtDuration(run.runtimeMs)}</span>
          <span>
            {run.dateFrom} → {run.dateTo}
          </span>
          <span>{fmtCurrency(run.initialCapital)}</span>
          <span>{run.benchmark}</span>
        </div>
        <ContextActions>
          <HonestyMarker />
          <Button
            variant="outline"
            size="sm"
            onClick={() => pushToast("Tearsheet exported", `backtest-${run.run}.pdf · snapshot pinned`)}
          >
            <Download className="h-3 w-3" />
            Export
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => pushToast("Re-run queued", `snapshot ${run.dataSnapshot} · identical config`)}
          >
            <RotateCcw className="h-3 w-3" />
            Re-run
          </Button>
          <IconButton onClick={toggleCopilot} title="Toggle Copilot">
            <PanelRight className="h-3.5 w-3.5" />
          </IconButton>
        </ContextActions>
      </ContextBar>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {/* Hero */}
        <Panel flush className="h-[380px] shrink-0">
          <div className="flex h-full flex-col">
            <div className="flex h-10 shrink-0 items-center justify-between border-b border-edge px-3.5">
              <div className="flex items-center gap-0.5">
                {MODES.map((mo) => (
                  <button
                    key={mo}
                    onClick={() => setMode(mo)}
                    className={cn(
                      "interactive cursor-pointer rounded px-2 py-1 text-xs",
                      mode === mo ? "text-text" : "text-text-3 hover:text-text-2",
                    )}
                  >
                    {mo}
                  </button>
                ))}
              </div>
              <div className="mono flex items-center gap-3 text-[10.5px] text-text-3">
                <span>equity, rebased 100</span>
                <span className="text-text-4">{run.dataSnapshot} · {run.engineVersion}</span>
              </div>
            </div>
            <div className="min-h-0 flex-1 p-1.5">{chartNode}</div>
          </div>
        </Panel>

        {/* Summary */}
        <MetricStrip className="shrink-0">
          <MetricCell label="Net Profit" value={fmtCurrency(run.initialCapital * m.totalReturn, 0, true)} tone={m.totalReturn >= 0 ? "pos" : "neg"} />
          <MetricCell label="CAGR" value={fmtPct(m.cagr)} tone={m.cagr >= 0 ? "pos" : "neg"} />
          <MetricCell label="Sharpe" value={m.sharpe.toFixed(2)} />
          <MetricCell label="Sortino" value={m.sortino.toFixed(2)} />
          <MetricCell label="Max DD" value={fmtPct(m.maxDrawdown, 1, false)} tone="neg" />
          <MetricCell label="Alpha" value={fmtPct(m.alpha)} tone={m.alpha >= 0 ? "pos" : "neg"} />
          <MetricCell label="Beta" value={m.beta.toFixed(2)} />
          <MetricCell label="Volatility" value={fmtPct(m.volatility, 1, false)} />
          <MetricCell label="Trades" value={String(m.trades)} />
        </MetricStrip>

        {/* Year table + heatmap */}
        <div className="grid grid-cols-2 gap-3">
          <Panel title="Performance by Year" flush>
            <DataTable
              dense
              rowKey={(r) => String(r.year)}
              rows={data.yearly}
              columns={[
                { key: "y", header: "Year", mono: true, render: (r) => <span className="text-text">{r.year}</span> },
                { key: "s", header: "Strategy", align: "right", mono: true, render: (r) => <span className={r.strategy >= 0 ? "text-pos" : "text-neg"}>{fmtPct(r.strategy, 1)}</span> },
                { key: "b", header: run.benchmark, align: "right", mono: true, render: (r) => <span className={r.benchmark >= 0 ? "text-pos" : "text-neg"}>{fmtPct(r.benchmark, 1)}</span> },
                { key: "e", header: "Excess", align: "right", mono: true, render: (r) => <span className={r.excess >= 0 ? "text-pos" : "text-neg"}>{fmtPct(r.excess, 1)}</span> },
                { key: "dd", header: "Max DD", align: "right", mono: true, render: (r) => <span className="text-neg">{fmtPct(r.maxDD, 1, false)}</span> },
                { key: "wr", header: "Win Days", align: "right", mono: true, render: (r) => fmtPct(r.winRate, 1, false) },
              ]}
            />
          </Panel>
          <Panel title="Monthly Returns" subtitle="net of costs" flush>
            <div className="p-3">
              <MonthlyHeatmap grid={data.monthly} />
            </div>
          </Panel>
        </div>

        {/* Distribution + drawdown periods */}
        <div className="grid grid-cols-2 gap-3">
          <Panel title="Trade Distribution" subtitle={`${m.trades} fills · win rate ${fmtPct(m.winRate, 1, false)}`}>
            <TradeDistribution trades={data.trades} />
          </Panel>
          <Panel title="Drawdown Periods" subtitle="top 5 by depth" flush>
            <DataTable
              dense
              rowKey={(d) => d.start}
              rows={ddPeriods}
              columns={[
                { key: "s", header: "Start", mono: true, render: (d) => fmtDate(d.start) },
                { key: "t", header: "Trough", mono: true, render: (d) => fmtDate(d.troughAt) },
                {
                  key: "r",
                  header: "Recovered",
                  mono: true,
                  render: (d) => (d.end ? fmtDate(d.end) : <span className="text-accent">ongoing</span>),
                },
                { key: "depth", header: "Depth", align: "right", mono: true, render: (d) => <span className="text-neg">{fmtPct(d.depth, 1, false)}</span> },
                { key: "len", header: "Days", align: "right", mono: true, render: (d) => d.lengthDays },
              ]}
            />
          </Panel>
        </div>

        <Panel title="Recent Trades" subtitle="most recent 10 fills" flush>
          <DataTable columns={tradeCols} rows={data.trades.slice(0, 10)} rowKey={(t) => t.id} dense />
        </Panel>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

interface DDPeriod {
  start: string;
  troughAt: string;
  end: string | null;
  depth: number;
  lengthDays: number;
}

function drawdownPeriods(dd: SeriesPoint[], top = 5): DDPeriod[] {
  const periods: DDPeriod[] = [];
  let start: string | null = null;
  let trough = 0;
  let troughAt = "";
  let lastT = dd[0]?.t ?? "";

  for (const p of dd) {
    if (p.v < -0.0005 && start === null) {
      start = lastT;
      trough = p.v;
      troughAt = p.t;
    } else if (p.v < -0.0005 && start !== null) {
      if (p.v < trough) {
        trough = p.v;
        troughAt = p.t;
      }
    } else if (p.v >= -0.0005 && start !== null) {
      periods.push({
        start,
        troughAt,
        end: p.t,
        depth: trough,
        lengthDays: daysBetween(start, p.t),
      });
      start = null;
    }
    lastT = p.t;
  }
  if (start !== null) {
    periods.push({
      start,
      troughAt,
      end: null,
      depth: trough,
      lengthDays: daysBetween(start, lastT),
    });
  }
  return periods.sort((a, b) => a.depth - b.depth).slice(0, top);
}

function daysBetween(a: string, b: string): number {
  return Math.round((new Date(b).getTime() - new Date(a).getTime()) / 86_400_000);
}
