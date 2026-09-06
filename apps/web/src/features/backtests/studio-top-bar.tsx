"use client";

import { Copy, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs } from "@/components/ui/tabs";
import { toast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";

export type StudioTab =
  | "curve"
  | "distribution"
  | "rolling"
  | "exposure"
  | "compare"
  | "mae-mfe"
  | "trades"
  | "monthly";

export function StudioTopBar({
  backtestId,
  dataVersion,
  engineVersion,
  tab,
  onTabChange,
  onExport,
}: {
  backtestId: string;
  dataVersion: string | null;
  engineVersion: string | null;
  tab: StudioTab;
  onTabChange: (tab: StudioTab) => void;
  onExport: () => void;
}) {
  const t = useT();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <Tabs
        value={tab}
        onChange={(id) => onTabChange(id as StudioTab)}
        items={[
          { id: "curve", label: t("backtest.tabs.curve") },
          { id: "distribution", label: t("backtest.tabs.distribution") },
          { id: "rolling", label: t("backtest.tabs.rolling") },
          { id: "exposure", label: t("backtest.tabs.exposure") },
          { id: "compare", label: t("backtest.tabs.compare") },
          { id: "mae-mfe", label: "MAE/MFE" },
          { id: "trades", label: t("backtest.tabs.trades") },
          { id: "monthly", label: t("backtest.tabs.monthly") },
        ]}
      />
      <div className="flex items-center gap-2 text-xs text-as-muted">
        <button
          type="button"
          className="inline-flex cursor-pointer items-center gap-1 rounded-lg px-2 py-1 hover:bg-as-secondary hover:text-as-text"
          onClick={() => {
            navigator.clipboard.writeText(dataVersion || "");
            toast(t("backtest.toast.dataFingerprintCopied"), "ok");
          }}
        >
          <Copy className="h-3 w-3" />
          {t("backtest.meta.data")} {dataVersion ? `${dataVersion.slice(0, 12)}…` : "—"}
        </button>
        <span>{t("backtest.meta.engine")} {engineVersion || "—"}</span>
        <Button variant="secondary" size="sm" onClick={onExport}>
          <Download className="h-3.5 w-3.5" />
          {t("backtest.action.exportCsv")}
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
  );
}
