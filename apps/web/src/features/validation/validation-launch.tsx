"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { request } from "@/lib/api/http";
import type { ValidationKind, ValidationRun } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { ValidationRunForm } from "./ValidationRunForm";

const selectClass =
  "h-9 w-full rounded-lg border border-as-border bg-as-bg px-3 text-sm text-as-text outline-none focus:border-as-primary/40 focus-visible:ring-2 focus-visible:ring-as-primary/20";

const MANUAL_KINDS: ValidationKind[] = [
  "walk_forward",
  "pbo",
  "sensitivity",
  "cost",
  "bootstrap",
  "regime",
  "spa",
];

export function ValidationLaunch({ kinds = MANUAL_KINDS }: { kinds?: ValidationKind[] }) {
  const qc = useQueryClient();

  const specsQuery = useQuery({
    queryKey: ["validation-specs"],
    queryFn: api.listValidationSpecs,
  });
  const strategiesQuery = useQuery({
    queryKey: ["strategies"],
    queryFn: api.listStrategies,
  });

  const specs = (specsQuery.data ?? []).filter(
    (s) => kinds.includes(s.kind as ValidationKind) && s.kind !== "dsr",
  );
  const strategies = strategiesQuery.data ?? [];

  const [strategyId, setStrategyId] = useState("");
  const [kind, setKind] = useState<ValidationKind | "">("");
  const [backtestId, setBacktestId] = useState("");

  const selected = strategies.find((s) => s.id === strategyId) ?? strategies[0];
  const strategyKey = selected?.id;
  const versionId = selected?.latest_version?.id;

  const backtestsQuery = useQuery({
    queryKey: ["backtests", strategyKey, "COMPLETED"],
    queryFn: () =>
      api.listBacktests({ strategy_id: strategyKey, status: "COMPLETED" }),
    enabled: Boolean(strategyKey),
  });
  const backtests = backtestsQuery.data ?? [];

  const availableKinds = specs.map((s) => s.kind as ValidationKind);
  const effectiveKind: ValidationKind | null = availableKinds.includes(kind as ValidationKind)
    ? (kind as ValidationKind)
    : (availableKinds[0] ?? null);
  const spec = effectiveKind ? specs.find((s) => s.kind === effectiveKind) : undefined;

  const chosenBacktest =
    backtests.find((b) => b.id === backtestId) ?? backtests[0];
  const chosenBacktestId = chosenBacktest?.id ?? "";

  const handleQueued = async (payload: unknown) => {
    await request<ValidationRun>("/api/v1/validation", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    qc.invalidateQueries({ queryKey: ["validation-runs"] });
    qc.invalidateQueries({ queryKey: ["pbo-runs"] });
    qc.invalidateQueries({ queryKey: ["backtests"] });
  };

  if (!specsQuery.data && specsQuery.isLoading) {
    return <Card className="h-40 animate-pulse bg-as-secondary" />;
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div className="space-y-1">
          <Label htmlFor="vlaunch-strategy">策略</Label>
          <select
            id="vlaunch-strategy"
            className={selectClass}
            value={selected?.id ?? ""}
            onChange={(e) => setStrategyId(e.target.value)}
          >
            {strategies.length ? (
              strategies.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name} · {row.status}
                </option>
              ))
            ) : (
              <option value="">还没有策略</option>
            )}
          </select>
        </div>

        <div className="space-y-1">
          <Label htmlFor="vlaunch-backtest">已完成回测</Label>
          <select
            id="vlaunch-backtest"
            className={selectClass}
            value={chosenBacktestId}
            onChange={(e) => setBacktestId(e.target.value)}
            disabled={!backtests.length}
          >
            {backtests.length ? (
              backtests.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.end_date ? b.start_date.slice(0, 10) : ""} →{" "}
                  {b.end_date ? b.end_date.slice(0, 10) : ""}
                  {b.sharpe != null ? ` · Sharpe ${Number(b.sharpe).toFixed(2)}` : ""}
                </option>
              ))
            ) : (
              <option value="">先跑完一次全样本回测</option>
            )}
          </select>
        </div>

        <div className="space-y-1">
          <Label htmlFor="vlaunch-kind">验证类型</Label>
          {availableKinds.length > 1 ? (
            <select
              id="vlaunch-kind"
              className={selectClass}
              value={effectiveKind ?? ""}
              onChange={(e) => setKind(e.target.value as ValidationKind)}
            >
              {availableKinds.map((k) => (
                <option key={k} value={k}>
                  {k.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          ) : (
            <input
              id="vlaunch-kind"
              className={selectClass}
              value={effectiveKind ? effectiveKind.replace(/_/g, " ") : ""}
              readOnly
            />
          )}
        </div>
      </div>

      {!strategies.length ? (
        <EmptyState
          title="还没有策略"
          description="先建一条策略并跑完一次回测，验证任务需要借用回测的标的池与数据快照。"
        />
      ) : !backtests.length ? (
        <EmptyState
          title="还没有已完成回测"
          description="验证借用回测的标的池与快照；部分类型还需要日期区间。先对该版本跑完一次全样本回测。"
        />
      ) : spec && versionId ? (
        <ValidationRunForm
          spec={spec}
          strategyVersionId={versionId}
          backtestId={chosenBacktestId}
          onSubmit={handleQueued}
        />
      ) : null}
    </div>
  );
}
