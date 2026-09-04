import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChevronLeft, Copy, Pencil, Play, Rocket, PanelRight } from "lucide-react";
import { cn } from "@/lib/cn";
import { fmtCurrency, fmtDate, fmtDateShort, fmtDuration, fmtPct, fmtTime } from "@/lib/format";
import { useApp } from "@/store/app";
import { getStrategy, getVersion } from "@/mocks/strategies";
import { backtestsFor, filterRange, getVersionData, rebase } from "@/mocks/engine";
import { hashSeed, mulberry32 } from "@/lib/prng";
import type { Backtest, StrategyParams, Trade } from "@/mocks/types";
import {
  ContextActions,
  ContextBar,
  ContextDivider,
  HonestyMarker,
} from "@/components/shell/context-bar";
import { Button, IconButton } from "@/components/ui/button";
import { Tabs, Segmented } from "@/components/ui/tabs";
import { Panel } from "@/components/ui/panel";
import { MetricCell, MetricStrip } from "@/components/ui/metric";
import { DataTable, type Column } from "@/components/ui/data-table";
import { RunBadge, StrategyBadge, Tag } from "@/components/ui/badge";
import { LineChart, COLORS } from "@/components/charts/line-chart";
import { MonthlyHeatmap } from "@/components/charts/monthly-heatmap";
import { TradeDistribution } from "@/components/charts/trade-distribution";

const TABS = ["Overview", "Performance", "Trades", "Parameters", "Experiments", "Logs"];

export function StrategyDetailPage() {
  const { id = "strat-momentum-alpha" } = useParams();
  const navigate = useNavigate();
  const { version, pushToast, toggleCopilot } = useApp();
  const [tab, setTab] = useState("Overview");

  const strategy = getStrategy(id);
  const v = getVersion(strategy, version);
  const data = getVersionData(v);
  const runs = useMemo(() => backtestsFor(strategy), [strategy]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ContextBar>
        <button
          onClick={() => navigate("/strategies")}
          className="interactive flex h-6.5 w-6.5 shrink-0 cursor-pointer items-center justify-center rounded-md text-text-3 hover:bg-raised hover:text-text"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <div className="flex min-w-0 items-center gap-2.5">
          <h1 className="truncate text-[13.5px] font-semibold text-text">{strategy.name}</h1>
          <StrategyBadge status={strategy.status} />
          <Tag tone="accent">{v.version}</Tag>
        </div>
        <ContextDivider />
        <div className="mono hidden shrink-0 items-center gap-3 text-[10.5px] text-text-3 lg:flex">
          <span>{strategy.id}</span>
          <span>created {fmtDateShort(strategy.createdAt)}</span>
          <span>last run {fmtTime(strategy.lastRun)}</span>
        </div>
        <ContextActions>
          <HonestyMarker />
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              pushToast("Backtest queued", `${strategy.name} ${v.version} · snap_3f9a2c41`);
              setTimeout(() => navigate(`/backtests/bt-${strategy.id}-184`), 900);
            }}
          >
            <Play className="h-3 w-3" />
            Run Backtest
          </Button>
          <Button variant="outline" size="sm" onClick={() => pushToast("Cloned", `${strategy.name} ${v.version} → draft copy`)}>
            <Copy className="h-3 w-3" />
            Clone
          </Button>
          <Button variant="outline" size="sm" onClick={() => setTab("Parameters")}>
            <Pencil className="h-3 w-3" />
            Edit
          </Button>
          <Button variant="outline" size="sm" onClick={() => pushToast("Deploy blocked", "Validation gates from Phase 3 stand in front of LIVE")}>
            <Rocket className="h-3 w-3" />
            Deploy
          </Button>
          <IconButton onClick={toggleCopilot} title="Toggle Copilot">
            <PanelRight className="h-3.5 w-3.5" />
          </IconButton>
        </ContextActions>
      </ContextBar>

      <Tabs items={TABS} value={tab} onChange={setTab} className="shrink-0 px-3.5" />

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {tab === "Overview" && (
          <OverviewTab
            strategyId={strategy.id}
            strategyName={strategy.name}
            benchmark={strategy.benchmark}
            version={v.version}
            data={data}
          />
        )}
        {tab === "Performance" && <PerformanceTab data={data} />}
        {tab === "Trades" && <TradesTab trades={data.trades} />}
        {tab === "Parameters" && (
          <ParametersTab
            params={v.params}
            version={v.version}
            onRun={() => pushToast("Backtest queued", `${strategy.name} ${v.version} · updated parameters`)}
          />
        )}
        {tab === "Experiments" && <ExperimentsTab runs={runs} onOpen={(bt) => navigate(`/backtests/${bt.id}`)} />}
        {tab === "Logs" && <LogsTab seed={`${strategy.id}-${v.version}`} />}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

type VData = ReturnType<typeof getVersionData>;

function OverviewTab({
  strategyName,
  benchmark,
  version,
  data,
}: {
  strategyId: string;
  strategyName: string;
  benchmark: string;
  version: string;
  data: VData;
}) {
  const range = "5Y";
  const equity = rebase(filterRange(data.equity, range));
  const spy = rebase(filterRange(data.benchmark, range));
  // QQQ as higher-beta tech proxy derived from the benchmark path
  const qqq = spy.map((p) => ({ t: p.t, v: 100 * Math.pow(p.v / 100, 1.24) }));

  return (
    <div className="space-y-3">
      <Panel flush className="h-[380px]">
        <div className="flex h-full flex-col">
          <div className="mono flex h-10 shrink-0 items-center justify-end gap-4 px-3.5 text-[10.5px] text-text-3">
            <Legend swatch="bg-accent" label={`${strategyName} ${version}`} />
            <Legend swatch="bg-[#6b7280]" label={benchmark} dashed />
            <Legend swatch="bg-[#8a94a6]" label="QQQ" dashed />
          </div>
          <div className="min-h-0 flex-1 p-1.5">
            <LineChart
              series={[
                { data: equity, color: COLORS.accent, area: true, lineWidth: 2 },
                { data: spy, color: COLORS.bench, lineWidth: 1, dashed: true },
                { data: qqq, color: "#8a94a6", lineWidth: 1, dotted: true },
              ]}
            />
          </div>
        </div>
      </Panel>

      <div className="grid grid-cols-2 gap-3">
        <Panel title="Monthly Returns" flush>
          <div className="p-3">
            <MonthlyHeatmap grid={data.monthly} />
          </div>
        </Panel>
        <Panel title="Drawdown" subtitle={`max ${fmtPct(data.metrics.maxDrawdown, 1, false)}`} flush className="h-[300px]">
          <div className="h-[calc(100%-40px)] p-1.5">
            <LineChart
              baseline
              series={[
                { data: filterRange(data.drawdown, range), color: COLORS.neg, area: true, lineWidth: 1 },
                { data: filterRange(data.benchmarkDrawdown, range), color: COLORS.bench, lineWidth: 1, dashed: true },
              ]}
            />
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Panel title="Rolling Sharpe" subtitle="63-day window" flush className="h-[240px]">
          <div className="h-[calc(100%-40px)] p-1.5">
            <LineChart series={[{ data: data.rolling, color: COLORS.info, area: true, lineWidth: 1 }]} />
          </div>
        </Panel>
        <Panel title="Exposure" subtitle="gross, fraction of NAV" flush className="h-[240px]">
          <div className="h-[calc(100%-40px)] p-1.5">
            <LineChart series={[{ data: data.exposure, color: COLORS.pos, area: true, lineWidth: 1 }]} />
          </div>
        </Panel>
      </div>

      <Panel title="Recent Trades" flush>
        <TradesTable trades={data.trades.slice(0, 8)} dense />
      </Panel>
    </div>
  );
}

function Legend({ swatch, label, dashed }: { swatch: string; label: string; dashed?: boolean }) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className={cn("h-px w-4", swatch)}
        style={dashed ? { backgroundImage: "linear-gradient(90deg, currentColor 55%, transparent 0)", backgroundSize: "4px 1px", backgroundColor: "transparent" } : undefined}
      />
      {label}
    </span>
  );
}

/* ------------------------------------------------------------------ */

function PerformanceTab({ data }: { data: VData }) {
  const m = data.metrics;
  return (
    <div className="space-y-3">
      <MetricStrip>
        <MetricCell label="Net Profit" value={fmtCurrency(250_000 * m.totalReturn, 0, true)} tone={m.totalReturn >= 0 ? "pos" : "neg"} />
        <MetricCell label="CAGR" value={fmtPct(m.cagr)} tone={m.cagr >= 0 ? "pos" : "neg"} />
        <MetricCell label="Sharpe" value={m.sharpe.toFixed(2)} />
        <MetricCell label="Sortino" value={m.sortino.toFixed(2)} />
        <MetricCell label="Alpha" value={fmtPct(m.alpha)} tone={m.alpha >= 0 ? "pos" : "neg"} hint="Annualized, vs benchmark OLS" />
        <MetricCell label="Beta" value={m.beta.toFixed(2)} />
        <MetricCell label="Max DD" value={fmtPct(m.maxDrawdown, 1, false)} tone="neg" />
      </MetricStrip>

      <div className="grid grid-cols-2 gap-3">
        <Panel title="Performance by Year" flush>
          <DataTable
            dense
            rowKey={(r) => String(r.year)}
            rows={data.yearly}
            columns={[
              { key: "y", header: "Year", mono: true, render: (r) => <span className="text-text">{r.year}</span> },
              { key: "s", header: "Strategy", align: "right", mono: true, render: (r) => <span className={r.strategy >= 0 ? "text-pos" : "text-neg"}>{fmtPct(r.strategy, 1)}</span> },
              { key: "b", header: "Benchmark", align: "right", mono: true, render: (r) => <span className={r.benchmark >= 0 ? "text-pos" : "text-neg"}>{fmtPct(r.benchmark, 1)}</span> },
              { key: "e", header: "Excess", align: "right", mono: true, render: (r) => <span className={r.excess >= 0 ? "text-pos" : "text-neg"}>{fmtPct(r.excess, 1)}</span> },
              { key: "dd", header: "Max DD", align: "right", mono: true, render: (r) => <span className="text-neg">{fmtPct(r.maxDD, 1, false)}</span> },
              { key: "sh", header: "Sharpe", align: "right", mono: true, render: (r) => r.sharpe.toFixed(2) },
            ]}
          />
        </Panel>
        <Panel title="Trade Distribution" subtitle="P&L per trade, net">
          <TradeDistribution trades={data.trades} />
        </Panel>
      </div>

      <Panel title="Monthly Returns" flush>
        <div className="p-3">
          <MonthlyHeatmap grid={data.monthly} />
        </div>
      </Panel>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function TradesTable({ trades, dense }: { trades: Trade[]; dense?: boolean }) {
  const cols: Column<Trade>[] = [
    { key: "id", header: "ID", mono: true, render: (t) => <span className="text-text-3">{t.id}</span> },
    { key: "sym", header: "Symbol", mono: true, render: (t) => <span className="text-text">{t.symbol}</span> },
    { key: "side", header: "Side", render: (t) => <span className={cn("mono text-[11px]", t.side === "LONG" ? "text-pos" : "text-neg")}>{t.side}</span> },
    { key: "qty", header: "Qty", align: "right", mono: true, render: (t) => t.qty.toLocaleString() },
    { key: "ed", header: "Entry", mono: true, render: (t) => fmtDate(t.entryDate) },
    { key: "ep", header: "Entry Px", align: "right", mono: true, render: (t) => `$${t.entryPrice.toFixed(2)}` },
    { key: "xd", header: "Exit", mono: true, render: (t) => fmtDate(t.exitDate) },
    { key: "xp", header: "Exit Px", align: "right", mono: true, render: (t) => `$${t.exitPrice.toFixed(2)}` },
    { key: "hold", header: "Days", align: "right", mono: true, render: (t) => t.holdingDays },
    { key: "pnl", header: "P&L", align: "right", mono: true, render: (t) => <span className={t.pnl >= 0 ? "text-pos" : "text-neg"}>{fmtCurrency(t.pnl, 0, true)}</span> },
    { key: "pct", header: "Return", align: "right", mono: true, render: (t) => <span className={t.pnlPct >= 0 ? "text-pos" : "text-neg"}>{fmtPct(t.pnlPct)}</span> },
  ];
  return <DataTable columns={cols} rows={trades} rowKey={(t) => t.id} dense={dense} />;
}

function TradesTab({ trades }: { trades: Trade[] }) {
  return (
    <Panel title={`Trades`} subtitle={`${trades.length} fills · net of costs`} flush>
      <TradesTable trades={trades} />
    </Panel>
  );
}

/* ------------------------------------------------------------------ */

function ParametersTab({ params, version, onRun }: { params: StrategyParams; version: string; onRun: () => void }) {
  const [p, setP] = useState(params);
  const dirty = JSON.stringify(p) !== JSON.stringify(params);

  return (
    <div className="grid max-w-[980px] grid-cols-2 gap-3">
      <Panel title="Signal" subtitle={`editing ${version} — unsaved changes stay local`}>
        <div className="space-y-5">
          <ParamSlider label="lookback" value={p.lookback} min={10} max={120} step={5} unit="d" onChange={(x) => setP({ ...p, lookback: x })} />
          <ParamSlider label="threshold" value={p.threshold} min={0.1} max={0.8} step={0.05} onChange={(x) => setP({ ...p, threshold: x })} />
          <ParamSlider label="stop_loss" value={p.stopLoss} min={0.02} max={0.1} step={0.005} pct onChange={(x) => setP({ ...p, stopLoss: x })} />
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="mono text-xs text-text-2">rebalance</span>
            </div>
            <Segmented
              items={["Daily", "Weekly", "Monthly"] as const}
              value={p.rebalance}
              onChange={(x) => setP({ ...p, rebalance: x })}
            />
          </div>
        </div>
      </Panel>
      <div className="space-y-3">
        <Panel title="Risk">
          <ParamSlider label="vol_target" value={p.volTarget} min={0.06} max={0.2} step={0.01} pct onChange={(x) => setP({ ...p, volTarget: x })} />
          <p className="mt-4 text-[11.5px] leading-relaxed text-text-3">
            Position sizes scale inversely with realized volatility until sleeve vol reaches target.
            Stops execute next bar, 5bps slippage, $1 flat fee.
          </p>
        </Panel>
        <Panel>
          <div className="flex items-center justify-between">
            <div className="text-[11.5px] text-text-3">
              {dirty ? "Unsaved parameter changes" : "Parameters match saved version"}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={!dirty} onClick={() => setP(params)}>
                Reset
              </Button>
              <Button variant="primary" size="sm" disabled={!dirty} onClick={onRun}>
                <Play className="h-3 w-3" />
                Save & Run
              </Button>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function ParamSlider({
  label,
  value,
  min,
  max,
  step,
  unit,
  pct,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  pct?: boolean;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="mono text-xs text-text-2">{label}</span>
        <span className="mono text-[13px] font-medium text-accent">
          {pct ? fmtPct(value, 1, false) : value}
          {unit ?? ""}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="axiom-range w-full"
      />
      <div className="mono mt-1 flex justify-between text-[9.5px] text-text-4">
        <span>{pct ? fmtPct(min, 1, false) : min}</span>
        <span>{pct ? fmtPct(max, 1, false) : max}</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function ExperimentsTab({ runs, onOpen }: { runs: Backtest[]; onOpen: (b: Backtest) => void }) {
  return (
    <Panel title="Experiment Runs" subtitle={`${runs.length} runs recorded in trial ledger`} flush>
      <DataTable
        rowKey={(b) => b.id}
        rows={runs}
        onRowClick={onOpen}
        columns={[
          { key: "run", header: "Run", mono: true, render: (b) => <span className="text-text">#{b.run}</span> },
          { key: "v", header: "Version", render: (b) => <Tag tone={b.status === "Completed" ? "default" : "neg"}>{b.version}</Tag> },
          { key: "st", header: "Status", render: (b) => <RunBadge status={b.status} /> },
          { key: "at", header: "Started", mono: true, render: (b) => `${fmtDate(b.startedAt)} ${fmtTime(b.startedAt)}` },
          { key: "rt", header: "Runtime", align: "right", mono: true, render: (b) => fmtDuration(b.runtimeMs) },
          { key: "snap", header: "Snapshot", mono: true, render: (b) => <span className="text-text-3">{b.dataSnapshot}</span> },
          { key: "eng", header: "Engine", mono: true, render: (b) => <span className="text-text-3">{b.engineVersion}</span> },
        ]}
      />
    </Panel>
  );
}

/* ------------------------------------------------------------------ */

function LogsTab({ seed }: { seed: string }) {
  const lines = useMemo(() => {
    const rand = mulberry32(hashSeed(`logs/${seed}`));
    const out: { t: string; level: "INFO" | "WARN" | "DEBUG"; msg: string }[] = [];
    const templates: [("INFO" | "WARN" | "DEBUG"), string][] = [
      ["INFO", "engine boot · lean-2.5.42+axiom.7"],
      ["INFO", "snapshot snap_3f9a2c41 verified · sha256 match · 2,209 trading days"],
      ["DEBUG", "universe resolved: 15 symbols, point-in-time membership OK"],
      ["INFO", "corporate actions applied: 41 dividends, 6 splits"],
      ["INFO", "warmup complete · indicators ready after 45 bars"],
      ["DEBUG", "rebalance: 15 → 15 names, turnover 4.2%"],
      ["WARN", "NVDA realized vol 2.1× target — position scaled to 0.62×"],
      ["INFO", "risk check passed · gross 0.83 ≤ 1.20 limit"],
      ["DEBUG", "fill model: next-bar open, 5.0bps slippage, $1.00 flat"],
      ["WARN", "2022-03 regime flag: trend filter active, beta 0.55 → 0.31"],
      ["INFO", "trial ledger append · trial_id=t-041 · snapshot= snap_3f9a2c41"],
      ["INFO", "tearsheet computed · 2,209 bars · 232 fills · 0 rejects"],
    ];
    const base = new Date("2026-09-03T14:22:00").getTime();
    templates.forEach(([level, msg], i) => {
      const t = new Date(base + i * (800 + rand() * 4200));
      out.push({
        t: t.toISOString().slice(11, 19) + "." + String(t.getMilliseconds()).padStart(3, "0"),
        level,
        msg,
      });
    });
    return out;
  }, [seed]);

  const levelColor = { INFO: "text-text-3", WARN: "text-accent", DEBUG: "text-text-4" } as const;

  return (
    <Panel title="Engine Log" subtitle="lean-2.5.42+axiom.7" flush>
      <div className="mono p-3 text-[11px] leading-[1.7]">
        {lines.map((l, i) => (
          <div key={i} className="flex gap-3">
            <span className="shrink-0 text-text-4">{l.t}</span>
            <span className={cn("w-11 shrink-0", levelColor[l.level])}>{l.level}</span>
            <span className="text-text-2">{l.msg}</span>
          </div>
        ))}
        <div className="mt-1 flex gap-3">
          <span className="text-text-4">—</span>
          <span className="text-pos">run complete · 0 errors, 0 warnings escalated</span>
        </div>
      </div>
    </Panel>
  );
}
