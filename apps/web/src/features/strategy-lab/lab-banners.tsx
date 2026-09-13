"use client";

import type { TrialStats } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatTemplate } from "@/lib/utils";
import { Disclosure } from "@/components/ui/disclosure";

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
        <Disclosure title={`试验记录 · ${trials.total_trials} 次`}>
          {firstSnapshot
            ? formatTemplate(t("strategy.trialsWithSnapshot"), {
                total: trials.total_trials,
                snapshot: firstSnapshot.snapshot_key || "—",
                snapshotCount: firstSnapshot.count,
              })
            : formatTemplate(t("strategy.trialsNoSnapshot"), {
                total: trials.total_trials,
              })}
        </Disclosure>
      ) : null}
      {legacyCode ? (
        <p className="text-xs text-as-negative">
          {t("strategy.legacyCodeBanner")}
        </p>
      ) : null}
    </>
  );
}
