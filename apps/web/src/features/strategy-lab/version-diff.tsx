"use client";

import { DiffEditor } from "@monaco-editor/react";
import type { StrategyVersion } from "@/lib/api";
import { diffLines } from "@/lib/diff";

export function VersionDiff({
  left,
  right,
}: {
  left: StrategyVersion;
  right: StrategyVersion;
}) {
  const [older, newer] = left.version <= right.version ? [left, right] : [right, left];
  const summary = diffLines(older.code, newer.code);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between gap-3 border-b border-as-border px-4 py-3">
        <div className="text-sm font-medium text-as-text">
          v{older.version} → v{newer.version}
        </div>
        <p className="text-[11px] tabular text-as-muted">
          +{summary.added} / −{summary.removed} 行
        </p>
      </div>
      <div className="min-h-0 flex-1">
        <DiffEditor
          height="100%"
          original={older.code}
          modified={newer.code}
          language="python"
          theme="vs"
          options={{
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 13,
            fontFamily: "SF Mono, Menlo, Monaco, Consolas, monospace",
            renderSideBySide: true,
            automaticLayout: true,
          }}
        />
      </div>
    </div>
  );
}
