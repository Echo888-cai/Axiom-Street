"use client";

import type { TrialStats } from "@/lib/api";

export function LabBanners({
  trials,
  legacyCode,
}: {
  trials?: TrialStats;
  legacyCode: boolean;
}) {
  const firstSnapshot = trials?.by_snapshot[0];
  return (
    <>
      {trials && trials.total_trials > 0 ? (
        <p className="text-xs text-as-muted">
          已在此策略族上试验 {trials.total_trials} 次
          {firstSnapshot
            ? `（当前快照 ${firstSnapshot.snapshot_key || "—"}：${firstSnapshot.count} 次）`
            : ""}
          。多次试验会抬高过拟合风险。
        </p>
      ) : null}
      {legacyCode ? (
        <p className="text-xs text-as-negative">
          当前代码使用了已失效的 AfterMarketClose。请点击「恢复 SPY
          200DMA」，否则回测会失败。
        </p>
      ) : null}
    </>
  );
}
