import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PanelRight, Play } from "lucide-react";
import { useApp } from "@/store/app";
import { getStrategy, getVersion, STRATEGIES } from "@/mocks/strategies";
import { filterRange, getVersionData, rebase, TRADING_DAYS } from "@/mocks/engine";
import { getCandles, getSymbol } from "@/mocks/market";
import { fmtCurrency, fmtDate, fmtPct } from "@/lib/format";
import { cn } from "@/lib/cn";
import type { TimeRange } from "@/mocks/types";
import {
  ContextActions,
  ContextBar,
  ContextDivider,
  HonestyMarker,
  SymbolContext,
} from "@/components/shell/context-bar";
import { Button, IconButton } from "@/components/ui/button";
import { Dropdown } from "@/components/ui/dropdown";
import { Segmented } from "@/components/ui/tabs";
import { Panel } from "@/components/ui/panel";
import { MetricCell, MetricStrip } from "@/components/ui/metric";
import { DataTable, type Column } from "@/components/ui/data-table";
import { LineChart, COLORS } from "@/components/charts/line-chart";
import { PriceChart } from "@/components/charts/price-chart";
import { MonthlyHeatmap } from "@/components/charts/monthly-heatmap";
import type { Trade } from "@/mocks/types";

const RANGES: readonly TimeRange[] = ["1D", "1W", "1M", "1Y", "5Y"] as const;
type ChartMode = "Price" | "Equity" | "Drawdown" | "Exposure";
const MODES: ChartMode[] = ["Price", "Equity", "Drawdown", "Exposure"];

export function ResearchPage() {
  const navigate = useNavigate();
  const {
    symbol,
    strategyId,
    version,
    range,
    setRange,
    setStrategy,
    setVersion,
    toggleCopilot,
    pushToast,
  } = useApp();
  const [mode, setMode] = useState<ChartMode>("Equity");

  const strategy = getStrategy(strategyId);
  const v = getVersion(strategy, version);
  const data = getVersionData(v);
  const info = getSymbol(symbol);

  const chartNode = useMemo(() => {
    if (mode === "Price") {
      return <PriceChart candles={getCandles(symbol, range === "1Y" ? 260 : range === "5Y" ? 500 : 500)} />;
    }
    if (mode === "Equity") {
      return (
        <LineChart
          series={[
            { data: rebase(filterRange(data.equity, range)), color: COLORS.accent, area: true, lineWidth: 2 },
            { data: rebase(filterRange(data.benchmark, range)), color: COLORS.bench, lineWidth: 1, dashed: true },
          ]}
        />
      );
    }
    if (mode === "Drawdown") {
      return (
        <LineChart
          baseline
          series={[
            { data: filterRange(data.drawdown, range), color: COLORS.neg, area: true, lineWidth: 1 },
            { data: filterRange(data.benchmarkDrawdown, range), color: COLORS.bench, lineWidth: 1, dashed: true },
          ]}
        />
      );
    }
    return (
      <LineChart
        series={[{ data: filterRange(data.exposure, range), color: COLORS.info, area: true, lineWidth: 1 }]}
      />
    );
  }, [mode, data, range, symbol]);

  const rangeLabel =
    range === "ALL" || range === "5Y"
      ? `${TRADING_DAYS[0]} → ${TRADING_DAYS[TRADING_DAYS.length - 1]}`
      : `${filterRange(data.equity, range)[0]?.t ?? ""} → ${TRADING_DAYS[TRADING_DAYS.length - 1]}`;

  const tradeCols: Column<Trade>[] = [
    { key: "sym", header: "Symbol", mono: true, render: (t) => <span className="text-text">{t.symbol}</span> },
    {
      key: "side",
      header: "Side",
      render: (t) => (
        <span className={cn("mono text-[11px]", t.side === "LONG" ? "text-pos" : "text-neg")}>{t.side}</span>
      ),
    },
    { key: "exit", header: "Closed", mono: true, render: (t) => fmtDate(t.exitDate) },
    {
      key: "pnl",
      header: "P&L",
      align: "right",
      mono: true,
      render: (t) => (
        <span className={t.pnl >= 0 ? "text-pos" : "text-neg"}>{fmtCurrency(t.pnl, 0, true)}</span>
      ),
    },
    {
      key: "pct",
      header: "Return",
      align: "right",
      mono: true,
      render: (t) => <span className={t.pnlPct >= 0 ? "text-pos" : "text-neg"}>{fmtPct(t.pnlPct)}</span> },
  ];

  const m = data.metrics;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ContextBar>
        <SymbolContext symbol={symbol} />
        <ContextDivider />
        <Segmented items={RANGES} value={range === "ALL" ? "5Y" : range} onChange={setRange} />
        <ContextDivider />
        <Dropdown
          prefix="Strategy"
          value={strategyId}
          items={STRATEGIES.map((s) => ({ value: s.id, label: s.name, hint: s.currentVersion }))}
          onChange={(id) => {
            const s = getStrategy(id);
            setStrategy(id, s.currentVersion);
          }}
        />
        <Dropdown
          value={version}
          items={strategy.versions.map((x) => ({ value: x.version, label: x.version }))}
          onChange={setVersion}
          className="w-[92px]"
        />
        <span className="mono hidden shrink-0 text-[10.5px] text-text-4 xl:inline">{rangeLabel}</span>
        <ContextActions>
          <HonestyMarker />
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              pushToast("Backtest queued", `${strategy.name} ${v.version} · snap_3f9a2c41 · lean-2.5.42`);
              setTimeout(() => navigate(`/backtests/bt-${strategyId}-184`), 900);
            }}
          >
            <Play className="h-3 w-3" />
            Run Backtest
          </Button>
          <IconButton onClick={toggleCopilot} title="Toggle Copilot">
            <PanelRight className="h-3.5 w-3.5" />
          </IconButton>
        </ContextActions>
      </ContextBar>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {/* Hero chart */}
        <Panel
          className="h-[400px] shrink-0"
          flush
          title={undefined}
          actions={undefined}
        >
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
                {mode !== "Price" ? (
                  <>
                    <span className="flex items-center gap-1.5">
                      <span className="h-px w-4 bg-accent" />
                      {strategy.name} {v.version}
                      <span className={m.totalReturn >= 0 ? "text-pos" : "text-neg"}>
                        {fmtPct(m.totalReturn, 1)}
                      </span>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="h-px w-4 bg-[#6b7280]" style={{ backgroundImage: "linear-gradient(90deg,#6b7280 60%,transparent 0)", backgroundSize: "4px 1px" }} />
                      {strategy.benchmark}
                    </span>
                  </>
                ) : (
                  <span>
                    {info.symbol} · US Equity · Daily · {info.sector}
                  </span>
                )}
              </div>
            </div>
            <div className="min-h-0 flex-1 p-1.5">{chartNode}</div>
          </div>
        </Panel>

        {/* Performance strip — density over cards */}
        <MetricStrip className="shrink-0">
          <MetricCell label="Total Return" value={fmtPct(m.totalReturn, 1)} tone={m.totalReturn >= 0 ? "pos" : "neg"} />
          <MetricCell label="CAGR" value={fmtPct(m.cagr, 1)} tone={m.cagr >= 0 ? "pos" : "neg"} />
          <MetricCell label="Sharpe" value={m.sharpe.toFixed(2)} />
          <MetricCell label="Sortino" value={m.sortino.toFixed(2)} />
          <MetricCell label="Max Drawdown" value={fmtPct(m.maxDrawdown, 1, false)} tone="neg" />
          <MetricCell label="Volatility" value={fmtPct(m.volatility, 1, false)} />
          <MetricCell label="Win Rate" value={fmtPct(m.winRate, 1, false)} />
          <MetricCell label="Profit Factor" value={m.profitFactor.toFixed(2)} />
        </MetricStrip>

        {/* Secondary row */}
        <div className="grid grid-cols-5 gap-3">
          <Panel
            title="Recent Trades"
            subtitle={`${m.trades} total`}
            flush
            className="col-span-3"
            actions={
              <Button variant="quiet" size="sm" onClick={() => navigate(`/strategies/${strategyId}`)}>
                View all
              </Button>
            }
          >
            <DataTable columns={tradeCols} rows={data.trades.slice(0, 7)} rowKey={(t) => t.id} dense onRowClick={() => navigate(`/strategies/${strategyId}`)} />
          </Panel>
          <Panel title="Monthly Returns" subtitle="strategy, net of costs" flush className="col-span-2">
            <div className="p-3">
              <MonthlyHeatmap grid={{ years: data.monthly.years.slice(-3), cells: data.monthly.cells }} />
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
