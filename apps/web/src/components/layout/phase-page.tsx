"use client";

import { useI18n } from "@/lib/i18n";
import { PhasePlaceholder } from "@/components/layout/phase-placeholder";

export type PhaseKind = "live" | "paper" | "risk";

export function PhasePage({ kind }: { kind: PhaseKind }) {
  const i18n = useI18n();
  const p = i18n.common.phase[kind];
  return (
    <PhasePlaceholder
      title={p.title}
      phase={p.phase}
      description={p.description}
      items={[...p.items]}
    />
  );
}
