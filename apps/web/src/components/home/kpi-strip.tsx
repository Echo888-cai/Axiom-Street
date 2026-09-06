"use client";

import { Activity, FlaskConical, TrendingDown, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/card";
import { formatNumber, formatPct } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

export function KpiStrip({
  totalReturn,
  sharpe,
  maxDrawdown,
  strategyCount,
  hasBacktest,
  unavailable,
}: {
  totalReturn: number | null;
  sharpe: number | null;
  maxDrawdown: number | null;
  strategyCount: number;
  hasBacktest: boolean;
  unavailable?: boolean;
}) {
  const t = useT();
  const items = [
    {
      key: "return",
      label: t("common.kpi.returnLabel"),
      icon: TrendingUp,
      value: hasBacktest ? formatPct(totalReturn) : "—",
      hint: hasBacktest ? t("common.kpi.returnHint") : t("common.kpi.pendingHint"),
      tone: hasBacktest
        ? (totalReturn ?? 0) >= 0
          ? "text-as-positive"
          : "text-as-negative"
        : "text-as-text",
    },
    {
      key: "sharpe",
      label: t("common.kpi.sharpeLabel"),
      icon: Activity,
      value: hasBacktest ? formatNumber(sharpe) : "—",
      hint: hasBacktest ? t("common.kpi.sharpeHint") : t("common.kpi.pendingHint"),
      tone: "text-as-text",
    },
    {
      key: "dd",
      label: t("common.kpi.drawdownLabel"),
      icon: TrendingDown,
      value: hasBacktest ? formatPct(maxDrawdown) : "—",
      hint: hasBacktest ? t("common.kpi.drawdownHint") : t("common.kpi.pendingHint"),
      tone: hasBacktest ? "text-as-negative" : "text-as-text",
    },
    {
      key: "strategies",
      label: t("common.kpi.strategiesLabel"),
      icon: FlaskConical,
      value: unavailable ? "—" : String(strategyCount),
      hint: strategyCount ? t("common.kpi.strategiesHint") : t("common.kpi.noStrategiesHint"),
      tone: "text-as-text",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 xl:grid-cols-4 as-stagger">
      {items.map((kpi) => {
        const Icon = kpi.icon;
        return (
          <Card key={kpi.key} className="min-h-[132px]">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs font-medium text-as-muted">
                {kpi.label}
              </span>
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-as-secondary/70 text-as-muted">
                <Icon className="h-3.5 w-3.5" />
              </span>
            </div>
            <div
              className={cn(
                "text-[28px] font-medium tabular tracking-tight",
                kpi.tone,
              )}
            >
              {kpi.value}
            </div>
            <p className="mt-1.5 text-[11px] text-as-muted">{kpi.hint}</p>
          </Card>
        );
      })}
    </div>
  );
}
