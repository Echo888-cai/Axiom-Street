"use client";

import { useQuery } from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

type PlanGate = {
  kind: string;
  display_name: string;
  applicable: boolean;
  reason_code: string;
  reason: string;
  supported_operators: string[];
  estimate: { lean_runs: number; est_minutes: number };
};

/** P3.3 整组计划：八项检验的适用条件、样本数要求、资源估计与冻结区间。 */
export function ValidationPlanCard({ strategyId }: { strategyId: string }) {
  const strategy = useQuery({
    queryKey: ["strategy", strategyId],
    queryFn: () => api.getStrategy(strategyId),
    enabled: Boolean(strategyId),
  });
  const versionId = strategy.data?.latest_version?.id;
  const plan = useQuery({
    queryKey: ["validation-plan", versionId],
    queryFn: () => api.validationPlan(versionId as string),
    enabled: Boolean(versionId),
  });
  const data = plan.data as
    | {
        trading_days?: number;
        trial_count?: number;
        gates?: PlanGate[];
        totals?: { gates_total: number; gates_applicable: number; lean_runs: number; est_minutes: number };
        frozen?: { start?: string | null; end?: string | null; note?: string };
      }
    | undefined;

  if (!strategyId) return null;
  return (
    <section className="rounded-as border border-as-border bg-as-bg p-5 shadow-as">
      <div className="flex items-center gap-2">
        <ClipboardList className="h-4 w-4 text-as-primary" aria-hidden="true" />
        <h2 className="text-sm font-semibold">整组验证计划</h2>
      </div>
      {!versionId ? (
        <p className="mt-3 text-xs text-as-muted">先选择一条策略。</p>
      ) : plan.isLoading ? (
        <p className="mt-3 text-xs text-as-muted">正在计算适用条件与资源估计…</p>
      ) : data ? (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
            <Badge tone="neutral">交易日 {data.trading_days}</Badge>
            <Badge tone="neutral">试验 {data.trial_count}</Badge>
            <Badge tone={data.totals?.gates_applicable === data.totals?.gates_total ? "green" : "amber"}>
              可运行 {data.totals?.gates_applicable}/{data.totals?.gates_total}
            </Badge>
            <Badge tone="blue">
              LEAN 约 {data.totals?.lean_runs} 次 · {data.totals?.est_minutes} 分钟
            </Badge>
            {data.frozen?.start && data.frozen?.end ? (
              <Badge tone="neutral">
                冻结区间 {data.frozen.start} → {data.frozen.end}
              </Badge>
            ) : null}
          </div>
          <ul className="mt-4 space-y-1.5">
            {(data.gates ?? []).map((gate) => (
              <li key={gate.kind} className="flex items-start gap-2 text-xs">
                <Badge tone={gate.applicable ? "green" : "amber"}>
                  {gate.applicable ? "可运行" : "不适用"}
                </Badge>
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{gate.display_name}</span>
                  <span className="ml-2 text-as-muted">
                    {gate.applicable
                      ? gate.estimate.lean_runs > 0
                        ? `约 ${gate.estimate.lean_runs} 次 LEAN · ${gate.estimate.est_minutes} 分钟`
                        : "无需 LEAN（基于现有结果计算）"
                      : gate.reason}
                  </span>
                  {gate.supported_operators.length > 0 && gate.applicable ? (
                    <span className="ml-2 text-as-muted">
                      算子：{gate.supported_operators.join(", ")}
                    </span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[10px] text-as-muted">{data.frozen?.note}</p>
        </>
      ) : null}
    </section>
  );
}
