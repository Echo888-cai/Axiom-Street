import { useNavigate } from "react-router-dom";
import { Plus, PanelRight } from "lucide-react";
import { fmtDateShort, fmtPct } from "@/lib/format";
import { useApp } from "@/store/app";
import { STRATEGIES } from "@/mocks/strategies";
import { getVersionData } from "@/mocks/engine";
import type { Strategy } from "@/mocks/types";
import { ContextActions, ContextBar, ContextDivider, HonestyMarker } from "@/components/shell/context-bar";
import { Button, IconButton } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { StrategyBadge, Tag } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";

export function StrategiesPage() {
  const navigate = useNavigate();
  const { pushToast, toggleCopilot, setStrategy } = useApp();

  const cols: Column<Strategy>[] = [
    {
      key: "name",
      header: "Strategy",
      render: (s) => (
        <div className="flex items-center gap-2.5">
          <span className="text-[13px] font-medium text-text">{s.name}</span>
          <StrategyBadge status={s.status} />
        </div>
      ),
    },
    { key: "v", header: "Version", render: (s) => <Tag tone="accent">{s.currentVersion}</Tag> },
    { key: "u", header: "Universe", render: (s) => <span className="text-text-3">{s.universe}</span> },
    { key: "bm", header: "Bench", mono: true, render: (s) => s.benchmark },
    { key: "lr", header: "Last Run", mono: true, render: (s) => fmtDateShort(s.lastRun) },
    {
      key: "sharpe",
      header: "Sharpe",
      align: "right",
      mono: true,
      render: (s) => {
        const m = getVersionData(s.versions.find((x) => x.version === s.currentVersion)!).metrics;
        return m.sharpe.toFixed(2);
      },
    },
    {
      key: "cagr",
      header: "CAGR",
      align: "right",
      mono: true,
      render: (s) => {
        const m = getVersionData(s.versions.find((x) => x.version === s.currentVersion)!).metrics;
        return <span className={m.cagr >= 0 ? "text-pos" : "text-neg"}>{fmtPct(m.cagr, 1)}</span>;
      },
    },
    {
      key: "dd",
      header: "Max DD",
      align: "right",
      mono: true,
      render: (s) => {
        const m = getVersionData(s.versions.find((x) => x.version === s.currentVersion)!).metrics;
        return <span className="text-neg">{fmtPct(m.maxDrawdown, 1, false)}</span>;
      },
    },
  ];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ContextBar>
        <h1 className="text-[13.5px] font-semibold text-text">My Strategies</h1>
        <ContextDivider />
        <span className="mono text-[10.5px] text-text-3">{STRATEGIES.length} strategies · 18 versions</span>
        <ContextActions>
          <HonestyMarker />
          <Button variant="primary" size="sm" onClick={() => pushToast("Draft created", "Untitled strategy · DRAFT")}>
            <Plus className="h-3 w-3" />
            New Strategy
          </Button>
          <IconButton onClick={toggleCopilot} title="Toggle Copilot">
            <PanelRight className="h-3.5 w-3.5" />
          </IconButton>
        </ContextActions>
      </ContextBar>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <Panel flush>
          <DataTable
            columns={cols}
            rows={STRATEGIES}
            rowKey={(s) => s.id}
            onRowClick={(s) => {
              setStrategy(s.id, s.currentVersion);
              navigate(`/strategies/${s.id}`);
            }}
          />
        </Panel>
      </div>
    </div>
  );
}
