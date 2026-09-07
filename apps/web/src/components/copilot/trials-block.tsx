"use client";

import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n";
import type { CopilotSnapshotFacts } from "@/lib/api/types";
import { PanelSectionTitle } from "./section-title";

export function TrialsBlock({
  rows,
  total,
}: {
  rows: CopilotSnapshotFacts[];
  total: number;
}) {
  const t = useT();
  if (rows.length === 0) {
    return (
      <section className="space-y-2">
        <PanelSectionTitle>{t("copilot.trials.title")}</PanelSectionTitle>
        <p className="rounded-xl border border-as-border bg-as-bg px-3 py-2.5 text-[13px] text-as-muted">
          {t("copilot.trials.none")}
        </p>
      </section>
    );
  }
  return (
    <section className="space-y-2">
      <PanelSectionTitle>{t("copilot.trials.title")}</PanelSectionTitle>
      <div className="rounded-xl border border-as-border bg-as-bg px-3 py-2.5">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-[13px] text-as-muted">
            {t("copilot.trials.total")}
          </span>
          <span className="font-mono text-lg tabular-nums tracking-tight text-as-text">
            {total}
          </span>
        </div>
      </div>
      {rows.length > 1 ? (
        <p className="px-0.5 text-[11px] text-as-muted">
          {t("copilot.trials.section")}
        </p>
      ) : null}
      <ul className="space-y-1.5">
        {rows.map((row) => (
          <li
            key={row.data_snapshot_id ?? row.snapshot_key ?? "unknown"}
            className="space-y-1.5 rounded-xl border border-as-border bg-as-bg px-3 py-2.5"
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="min-w-0 break-all font-mono text-[10.5px] leading-tight text-as-muted">
                {row.snapshot_key ?? "—"}
              </span>
              <span className="font-mono text-sm tabular-nums text-as-text">
                {row.count}
              </span>
            </div>
            {(row.duplicate_parameter_hashes > 0 || row.superseded_by_key) && (
              <div className="flex flex-wrap gap-1.5">
                {row.superseded_by_key ? (
                  <Badge tone="amber" className="text-[10px]">
                    {t("copilot.trials.superseded")}
                  </Badge>
                ) : null}
                {row.duplicate_parameter_hashes > 0 ? (
                  <Badge tone="amber" className="text-[10px]">
                    {t("copilot.trials.duplicate")} {row.duplicate_parameter_hashes}
                  </Badge>
                ) : null}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
