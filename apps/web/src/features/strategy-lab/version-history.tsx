"use client";

import { cn } from "@/lib/utils";
import type { StrategyVersion } from "@/lib/api";

export function VersionHistory({
  versions,
  currentId,
  compareIds,
  onSelect,
  onToggleCompare,
}: {
  versions: StrategyVersion[];
  currentId?: string;
  compareIds: string[];
  onSelect: (version: StrategyVersion) => void;
  onToggleCompare: (id: string) => void;
}) {
  if (!versions.length) {
    return <p className="p-4 text-xs text-as-muted">还没有版本记录。</p>;
  }
  return (
    <ul className="space-y-1 overflow-auto p-3">
      {versions.map((v) => {
        const comparing = compareIds.includes(v.id);
        return (
          <li key={v.id}>
            <div
              className={cn(
                "flex items-start gap-1 rounded-lg transition-colors duration-as",
                v.id === currentId ? "bg-[rgba(22,119,255,0.08)]" : "hover:bg-as-secondary",
                comparing && "ring-1 ring-as-primary/30",
              )}
            >
              <button
                type="button"
                aria-pressed={comparing}
                aria-label={`对比 v${v.version}`}
                onClick={() => onToggleCompare(v.id)}
                className="mt-0.5 flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center outline-none focus-visible:ring-2 focus-visible:ring-as-primary/30"
              >
                <span
                  className={cn(
                    "h-3.5 w-3.5 rounded border",
                    comparing ? "border-as-primary bg-as-primary" : "border-as-border bg-as-bg",
                  )}
                />
              </button>
              <button
                type="button"
                onClick={() => onSelect(v)}
                className="min-w-0 flex-1 cursor-pointer px-2 py-2.5 text-left"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-as-text">v{v.version}</span>
                  <span className="text-[10px] tabular text-as-muted">
                    {v.created_at.slice(0, 16).replace("T", " ")}
                  </span>
                </div>
                <p className="mt-0.5 truncate text-[11px] text-as-muted">
                  {v.commit_message || "无说明"}
                </p>
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
