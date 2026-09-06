"use client";

import { Card } from "@/components/ui/card";
import type { StrategyVersion } from "@/lib/api";
import { VersionHistory } from "./version-history";

export function VersionHistoryCard({
  versions,
  currentId,
  compareIds,
  onToggleCompare,
  onSelect,
}: {
  versions: StrategyVersion[];
  currentId?: string | null;  compareIds: string[];
  onToggleCompare: (id: string) => void;
  onSelect: (v: StrategyVersion) => void;
}) {
  return (
    <Card className="col-span-12 flex min-h-0 flex-col overflow-hidden p-0 lg:col-span-3">
      <div className="border-b border-as-border px-4 py-3">
        <div className="text-sm font-medium">版本历史</div>
        <p className="mt-0.5 text-[11px] text-as-muted">
          勾选两个版本对比；点击载入到编辑器
        </p>
      </div>
      <VersionHistory
        versions={versions}
        currentId={currentId ?? undefined}
        compareIds={compareIds}
        onToggleCompare={onToggleCompare}
        onSelect={onSelect}
      />
    </Card>
  );
}
