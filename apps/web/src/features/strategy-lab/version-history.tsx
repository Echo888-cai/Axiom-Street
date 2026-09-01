"use client";

import { cn } from "@/lib/utils";
import type { StrategyVersion } from "@/lib/api";

export function VersionHistory({
  versions,
  currentId,
  onSelect,
}: {
  versions: StrategyVersion[];
  currentId?: string;
  onSelect: (version: StrategyVersion) => void;
}) {
  if (!versions.length) {
    return <p className="p-4 text-xs text-aq-muted">还没有版本记录。</p>;
  }
  return (
    <ul className="space-y-1 overflow-auto p-3">
      {versions.map((v) => (
        <li key={v.id}>
          <button
            type="button"
            onClick={() => onSelect(v)}
            className={cn(
              "w-full cursor-pointer rounded-lg px-3 py-2.5 text-left transition-colors duration-aq",
              v.id === currentId ? "bg-[rgba(22,119,255,0.08)]" : "hover:bg-aq-secondary",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-aq-text">v{v.version}</span>
              <span className="text-[10px] tabular text-aq-muted">
                {v.created_at.slice(0, 16).replace("T", " ")}
              </span>
            </div>
            <p className="mt-0.5 truncate text-[11px] text-aq-muted">
              {v.commit_message || "无说明"}
            </p>
          </button>
        </li>
      ))}
    </ul>
  );
}
