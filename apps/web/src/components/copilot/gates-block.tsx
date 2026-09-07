"use client";

import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n";
import type { CopilotGateFacts } from "@/lib/api/types";
import { PanelSectionTitle } from "./section-title";

// OpenAPI kinds are uppercase; the validation dictionary keys are lowercase.
const KIND_LABEL_KEY: Record<string, string> = {
  DSR: "dsr",
  PBO: "pbo",
  WALK_FORWARD: "walk_forward",
  SENSITIVITY: "sensitivity",
  COST: "cost",
  BOOTSTRAP: "bootstrap",
  REGIME: "regime",
  SPA: "spa",
};

function GateBadge({ gate }: { gate: CopilotGateFacts }) {
  const t = useT();
  if (gate.status === "COMPLETED") {
    return (
      <Badge tone={gate.passed ? "green" : "red"}>
        {gate.passed ? t("copilot.gates.passed") : t("copilot.gates.failed")}
      </Badge>
    );
  }
  return <Badge tone="amber">{t("copilot.gates.running")}</Badge>;
}

export function GatesBlock({ gates }: { gates: CopilotGateFacts[] }) {
  const t = useT();
  if (gates.length === 0) {
    return (
      <section className="space-y-2">
        <PanelSectionTitle>{t("copilot.gates.title")}</PanelSectionTitle>
        <p className="rounded-xl border border-as-border bg-as-bg px-3 py-2.5 text-[13px] text-as-muted">
          {t("copilot.gates.none")}
        </p>
      </section>
    );
  }
  return (
    <section className="space-y-2">
      <PanelSectionTitle>{t("copilot.gates.title")}</PanelSectionTitle>
      <ul className="space-y-1.5">
        {gates.map((gate) => {
          const labelKey = KIND_LABEL_KEY[gate.kind] ?? gate.kind;
          return (
            <li
              key={gate.kind}
              className="flex items-center justify-between gap-2 rounded-xl border border-as-border bg-as-bg px-3 py-2"
            >
              <span className="truncate text-[13px] text-as-text">
                {t(`validation.kinds.${labelKey}`)}
              </span>
              <GateBadge gate={gate} />
            </li>
          );
        })}
      </ul>
    </section>
  );
}
