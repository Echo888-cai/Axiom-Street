"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-as border border-as-border bg-as-bg px-3 py-2.5 shadow-as">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-1.5 text-[11px] text-as-muted">
          开始
          <Input
            type="date"
            className="w-[138px]"
            value={props.startDate}
            onChange={(e) => props.onStartDate(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-1.5 text-[11px] text-as-muted">
          结束
          <Input
            type="date"
            className="w-[138px]"
            value={props.endDate}
            onChange={(e) => props.onEndDate(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-1.5 text-[11px] text-as-muted">
          本金
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
          标的池
          <select
            className="h-9 rounded-lg border border-as-border bg-as-bg px-2 text-sm text-as-text outline-none focus:border-as-primary/40"
            value={props.universeId}
            onChange={(e) => props.onUniverseId(e.target.value)}
          >
            <option value="">快照全部标的</option>
            {props.universes.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
                {item.member_count ? `（${item.member_count}）` : ""}
              </option>
            ))}
          </select>
        </label>
        <Input
          className="w-44"
          value={props.message}
          onChange={(e) => props.onMessage(e.target.value)}
          placeholder="版本说明"
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="ghost" onClick={() => props.onRestore("spy")}>
          恢复 SPY 200DMA
        </Button>
        <Button variant="ghost" onClick={() => props.onRestore("equal")}>
          加载等权横截面
        </Button>
        <Button
          variant="secondary"
          onClick={props.onSave}
          disabled={props.savePending || !props.dirty}
        >
          {props.savePending ? "保存中…" : "保存版本"}
        </Button>
        <Button onClick={props.onRun} disabled={props.runPending}>
          {props.runPending ? "提交中…" : "运行回测"}
        </Button>
      </div>
    </div>
  );
}
