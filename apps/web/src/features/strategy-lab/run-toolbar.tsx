"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useT } from "@/lib/i18n";
import type { Universe } from "@/lib/api";

interface RunToolbarProps {
  startDate: string;
  endDate: string;
  capital: string;
  universeId: string;
  message: string;
  universes: Universe[];
  onStartDate: (v: string) => void;
  onEndDate: (v: string) => void;
  onCapital: (v: string) => void;
  onUniverseId: (v: string) => void;
  onMessage: (v: string) => void;
  dirty: boolean;
  savePending: boolean;
  onSave: () => void;
  runPending: boolean;
  onRun: () => void;
  onRestore: (kind: "spy" | "equal") => void;
}

export function RunToolbar(props: RunToolbarProps) {
  const t = useT();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-as border border-as-border bg-as-bg px-3 py-2.5 shadow-as">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-1.5 text-[11px] text-as-muted">
          {t("strategy.startDate")}
          <Input
            type="date"
            className="w-[138px]"
            value={props.startDate}
            onChange={(e) => props.onStartDate(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-1.5 text-[11px] text-as-muted">
          {t("strategy.endDate")}
          <Input
            type="date"
            className="w-[138px]"
            value={props.endDate}
            onChange={(e) => props.onEndDate(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-1.5 text-[11px] text-as-muted">
          {t("strategy.capital")}
          <Input
            type="number"
            min={1000}
            step={1000}
            className="w-28"
            value={props.capital}
            onChange={(e) => props.onCapital(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-1.5 text-[11px] text-as-muted">
          {t("strategy.universeFieldLabel")}
          <select
            className="h-9 rounded-lg border border-as-border bg-as-bg px-2 text-sm text-as-text outline-none focus:border-as-primary/40"
            value={props.universeId}
            onChange={(e) => props.onUniverseId(e.target.value)}
          >
            <option value="">{t("strategy.universeAllSnapshot")}</option>
            {props.universes.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
                {item.member_count ? ` (${item.member_count})` : ""}
              </option>
            ))}
          </select>
        </label>
        <Input
          className="w-44"
          value={props.message}
          onChange={(e) => props.onMessage(e.target.value)}
          placeholder={t("strategy.versionNotePlaceholder")}
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="ghost" onClick={() => props.onRestore("spy")}>
          {t("strategy.restoreSpyTemplate")}
        </Button>
        <Button variant="ghost" onClick={() => props.onRestore("equal")}>
          {t("strategy.loadEqualTemplate")}
        </Button>
        <Button
          variant="secondary"
          onClick={props.onSave}
          disabled={props.savePending || !props.dirty}
        >
          {props.savePending
            ? t("strategy.savingLabel")
            : t("strategy.saveVersionButton")}
        </Button>
        <Button onClick={props.onRun} disabled={props.runPending}>
          {props.runPending
            ? t("strategy.submittingLabel")
            : t("strategy.runBacktestButton")}
        </Button>
      </div>
    </div>
  );
}
