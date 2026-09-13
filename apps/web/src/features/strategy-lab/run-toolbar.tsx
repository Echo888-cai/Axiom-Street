"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useT } from "@/lib/i18n";
import { validateExperiment } from "./guided-strategy";
import { Play, Settings2 } from "lucide-react";
import type { Universe } from "@/lib/api";

interface RunToolbarProps {
  blocked?: boolean;
  professional?: boolean;
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
  const valid = validateExperiment(props.startDate, props.endDate, props.capital);
  return (
    <section className="rounded-as border border-as-border bg-as-bg p-6 shadow-as">
      <div className="mb-5"><div className="mb-2 text-[11px] font-medium tracking-widest text-as-muted">02 / 回测</div><h2 className="text-xl font-semibold">设置历史实验</h2></div>
      <div className="grid grid-cols-2 gap-4">
        <label className="flex flex-col items-start gap-2 text-xs text-as-muted">
          {t("strategy.startDate")}
          <Input
            type="date"
            className="w-full min-w-0"
            value={props.startDate}
            onChange={(e) => props.onStartDate(e.target.value)}
          />
        </label>
        <label className="flex flex-col items-start gap-2 text-xs text-as-muted">
          {t("strategy.endDate")}
          <Input
            type="date"
            className="w-full min-w-0"
            value={props.endDate}
            onChange={(e) => props.onEndDate(e.target.value)}
          />
        </label>
        <label className="flex flex-col items-start gap-2 text-xs text-as-muted">
          {t("strategy.capital")}
          <Input
            type="number"
            min={1000}
            step={1000}
            className="w-full"
            value={props.capital}
            onChange={(e) => props.onCapital(e.target.value)}
          />
        </label>
        <label className="flex flex-col items-start gap-2 text-xs text-as-muted">
          {t("strategy.universeFieldLabel")}
          <select
            className="as-field as-select h-11 w-full min-w-0 rounded-xl border border-as-border bg-as-bg px-3 text-sm text-as-text"
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

      </div>
      <details className="my-5 rounded-xl border border-as-border p-4"><summary className="flex cursor-pointer items-center gap-2 text-sm"><Settings2 className="h-4 w-4" />版本备注与保存</summary><div className="mt-4 flex flex-wrap items-end gap-3"><label className="text-xs text-as-muted">版本备注<Input className="mt-2 w-full" value={props.message} onChange={(e) => props.onMessage(e.target.value)} /></label><Button variant="secondary" onClick={props.onSave} disabled={props.savePending || !props.dirty || props.blocked}>保存版本</Button></div></details>
      {props.professional && <div className="mb-4 flex flex-wrap gap-2">
        <Button variant="ghost" onClick={() => props.onRestore("spy")}>
          {t("strategy.restoreSpyTemplate")}
        </Button>
        <Button variant="ghost" onClick={() => props.onRestore("equal")}>
          {t("strategy.loadEqualTemplate")}
        </Button>
      </div>}
      {!valid && <p role="alert" className="mb-4 text-sm text-as-negative">结束日期必须晚于开始日期，本金至少为 1,000。</p>}
      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-as-border pt-5">
        <p className="text-xs leading-6 text-as-muted">{props.blocked ? "请先应用或撤销规则草稿。" : "运行时自动保存版本与试验记录。"}</p>
        <Button className="w-full" onClick={props.onRun} disabled={props.runPending || props.savePending || props.blocked || !valid}>
          <Play className="h-4 w-4" aria-hidden="true" />{props.runPending
            ? t("strategy.submittingLabel")
            : "运行实验"}
        </Button>
      </div>
    </section>
  );
}
