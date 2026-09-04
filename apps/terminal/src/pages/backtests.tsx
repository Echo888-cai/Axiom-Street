import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { PanelRight } from "lucide-react";
import { fmtDate, fmtDuration, fmtTime } from "@/lib/format";
import { useApp } from "@/store/app";
import { STRATEGIES } from "@/mocks/strategies";
import { backtestsFor } from "@/mocks/engine";
import type { Backtest } from "@/mocks/types";
import { ContextActions, ContextBar, ContextDivider, HonestyMarker } from "@/components/shell/context-bar";
import { IconButton } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { RunBadge, Tag } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";

export function BacktestsPage() {
  const navigate = useNavigate();
  const { toggleCopilot } = useApp();

  const runs = useMemo(
    () =>
      STRATEGIES.flatMap((s) => backtestsFor(s))
        .sort((a, b) => +new Date(b.startedAt) - +new Date(a.startedAt))
        .slice(0, 24),
    [],
  );

  const cols: Column<Backtest>[] = [
    { key: "run", header: "Run", mono: true, render: (b) => <span className="text-text">#{b.run}</span> },
    { key: "s", header: "Strategy", render: (b) => STRATEGIES.find((s) => s.id === b.strategyId)?.name ?? b.strategyId },
    { key: "v", header: "Version", render: (b) => <Tag>{b.version}</Tag> },
    { key: "st", header: "Status", render: (b) => <RunBadge status={b.status} /> },
    { key: "range", header: "Range", mono: true, render: (b) => <span className="text-text-3">{b.dateFrom.slice(0, 4)} → {b.dateTo.slice(0, 4)}</span> },
    { key: "at", header: "Started", mono: true, render: (b) => `${fmtDate(b.startedAt)} ${fmtTime(b.startedAt)}` },
    { key: "rt", header: "Runtime", align: "right", mono: true, render: (b) => fmtDuration(b.runtimeMs) },
    { key: "snap", header: "Snapshot", mono: true, render: (b) => <span className="text-text-3">{b.dataSnapshot}</span> },
  ];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ContextBar>
        <h1 className="text-[13.5px] font-semibold text-text">Backtests</h1>
        <ContextDivider />
        <span className="mono text-[10.5px] text-text-3">trial ledger · every run counts toward the multiple-testing budget</span>
        <ContextActions>
          <HonestyMarker />
          <IconButton onClick={toggleCopilot} title="Toggle Copilot">
            <PanelRight className="h-3.5 w-3.5" />
          </IconButton>
        </ContextActions>
      </ContextBar>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <Panel flush>
          <DataTable columns={cols} rows={runs} rowKey={(b) => b.id} onRowClick={(b) => navigate(`/backtests/${b.id}`)} />
        </Panel>
      </div>
    </div>
  );
}
