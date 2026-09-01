"use client";

import { Activity, FlaskConical, TrendingDown, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/card";
import { formatNumber, formatPct } from "@/lib/utils";
import { cn } from "@/lib/utils";

export function KpiStrip({
  totalReturn,
  sharpe,
  maxDrawdown,
  strategyCount,
  hasBacktest,
}: {
  totalReturn: number | null;
  sharpe: number | null;
  maxDrawdown: number | null;
  strategyCount: number;
  hasBacktest: boolean;
}) {
  const items = [
    {
      key: "return",
      label: "最近回测收益",
      icon: TrendingUp,
      value: hasBacktest ? formatPct(totalReturn) : "—",
      hint: hasBacktest ? "研究指标，非实盘组合" : "跑完第一次回测后显示",
      tone: hasBacktest ? ((totalReturn ?? 0) >= 0 ? "text-aq-positive" : "text-aq-negative") : "text-aq-text",
    },
    {
      key: "sharpe",
      label: "夏普",
      icon: Activity,
      value: hasBacktest ? formatNumber(sharpe) : "—",
      hint: hasBacktest ? "年化超额 / 波动" : "跑完第一次回测后显示",
      tone: "text-aq-text",
    },
    {
      key: "dd",
      label: "最大回撤",
      icon: TrendingDown,
      value: hasBacktest ? formatPct(maxDrawdown) : "—",
      hint: hasBacktest ? "从峰值回落的最大幅度" : "跑完第一次回测后显示",
      tone: hasBacktest ? "text-aq-negative" : "text-aq-text",
    },
    {
      key: "strategies",
      label: "策略数量",
      icon: FlaskConical,
      value: String(strategyCount),
      hint: strategyCount ? "实验室中的策略" : "还没有策略",
      tone: "text-aq-text",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4 aq-stagger">
      {items.map((kpi) => {
        const Icon = kpi.icon;
        return (
          <Card key={kpi.key} className="min-h-[108px]">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs font-medium text-aq-muted">{kpi.label}</span>
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-aq-secondary text-aq-muted">
                <Icon className="h-3.5 w-3.5" />
              </span>
            </div>
            <div className={cn("text-2xl font-semibold tabular tracking-tight", kpi.tone)}>
              {kpi.value}
            </div>
            <p className="mt-1.5 text-[11px] text-aq-muted">{kpi.hint}</p>
          </Card>
        );
      })}
    </div>
  );
}
