"use client";

import type { TrialStats } from "@/lib/api";
import { useT } from "@/lib/i18n";

function fmt(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) =>
    String(vars[key] ?? ""),
  );
}

export function LabBanners({
  trials,
  legacyCode,
}: {
  trials?: TrialStats;
  legacyCode: boolean;
}) {
  const t = useT();
  const firstSnapshot = trials?.by_snapshot?.[0];
  return (
    <>
      {trials && trials.total_trials > 0 ? (
        <p className="text-xs text-as-muted">
          {firstSnapshot
            ? fmt(t("strategy.trialsWithSnapshot"), {
                total: trials.total_trials,
                snapshot: firstSnapshot.snapshot_key || "—",
                snapshotCount: firstSnapshot.count,
              })
            : fmt(t("strategy.trialsNoSnapshot"), {
                total: trials.total_trials,
              })}
        </p>
      ) : null}
      {legacyCode ? (
        <p className="text-xs text-as-negative">
          {t("strategy.legacyCodeBanner")}
        </p>
      ) : null}
    </>
  );
}
