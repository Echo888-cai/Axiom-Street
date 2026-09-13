"use client";

import { Activity, FlaskConical, TrendingDown, TrendingUp } from "lucide-react";
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
  const available = hasBacktest && !unavailable;
  const items = [
    {
      key: "return",
      label: t("common.kpi.returnLabel"),
      icon: TrendingUp,
      value: available ? formatPct(totalReturn) : "—",
      hint: available
        ? t("common.kpi.returnHint")
        : t("common.kpi.pendingHint"),
      tone: available
        ? (totalReturn ?? 0) >= 0
          ? "text-as-positive"
          : "text-as-negative"
        : "text-as-text",
    },
    {
      key: "sharpe",
      label: t("common.kpi.sharpeLabel"),
      icon: Activity,
      value: available ? formatNumber(sharpe) : "—",
      hint: available
        ? t("common.kpi.sharpeHint")
        : t("common.kpi.pendingHint"),
      tone: "text-as-text",
    },
    {
      key: "dd",
      label: t("common.kpi.drawdownLabel"),
      icon: TrendingDown,
      value: available ? formatPct(maxDrawdown) : "—",
      hint: available
        ? t("common.kpi.drawdownHint")
        : t("common.kpi.pendingHint"),
      tone: available ? "text-as-negative" : "text-as-text",
    },
    {
      key: "strategies",
      label: t("common.kpi.strategiesLabel"),
      icon: FlaskConical,
      value: unavailable ? "—" : String(strategyCount),
      hint: strategyCount
        ? t("common.kpi.strategiesHint")
        : t("common.kpi.noStrategiesHint"),
      tone: "text-as-text",
    },
  ];

  return (
    <dl
      aria-label="研究指标"
      className="as-metric-strip grid grid-cols-2 lg:grid-cols-4"
    >
      {items.map((kpi) => {
        const Icon = kpi.icon;
        return (
          <div
            key={kpi.key}
            className="as-metric-cell"
            data-tone={
              kpi.tone === "text-as-negative"
                ? "negative"
                : kpi.tone === "text-as-text"
                  ? "neutral"
                  : "positive"
            }
          >
            <dt className="flex items-center justify-between gap-2 text-xs font-medium text-as-muted">
              {kpi.label}
              <span className="as-metric-icon">
                <Icon className="h-4 w-4" aria-hidden="true" />
              </span>
            </dt>
            <dd>
              <div
                className={cn(
                  "mt-4 text-[28px] font-medium leading-none tabular tracking-[-.06em] sm:text-[32px]",
                  kpi.tone,
                )}
              >
                {kpi.value}
              </div>
              <p className="mt-3 text-[11px] leading-5 text-as-muted">
                {unavailable ? "数据暂不可用" : kpi.hint}
              </p>
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
