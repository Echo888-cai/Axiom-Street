"use client";

import { Card } from "@/components/ui/card";
import { useT } from "@/lib/i18n";
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
  const t = useT();
  return (
    <Card className="col-span-12 flex min-h-0 flex-col overflow-hidden p-0 lg:col-span-3">
      <div className="border-b border-as-border px-4 py-3">
        <div className="text-sm font-medium">{t("strategy.versions")}</div>
        <p className="mt-0.5 text-[11px] text-as-muted">
          {t("strategy.versionHistoryHint")}
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
