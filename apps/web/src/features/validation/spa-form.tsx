"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";

const selectClass =
  "h-9 w-full rounded-lg border border-as-border bg-as-bg px-3 text-sm text-as-text outline-none focus:border-as-primary/40 focus-visible:ring-2 focus-visible:ring-as-primary/20";

export function SpaForm() {
  const qc = useQueryClient();
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.listStrategies });
  const [strategyId, setStrategyId] = useState("");

  const items = strategies.data ?? [];
  const selected = items.find((row) => row.id === strategyId) ?? items[0];
  const versionId = selected?.latest_version?.id;

  const backtests = useQuery({
    queryKey: ["backtests", selected?.id, "COMPLETED"],
    queryFn: () => api.listBacktests({ strategy_id: selected?.id, status: "COMPLETED" }),
    enabled: Boolean(selected?.id),
  });
  const latest = backtests.data?.[0];

  useEffect(() => {
    if (!selected && items[0]) setStrategyId(items[0].id);
  }, [items, selected]);

  const hint = useMemo(() => {
    if (!items.length) return "先建一条策略。";
    if (!latest) {
      return "先对该版本跑完一次全样本回测。Reality Check 读取同一家族、同一数据快照上的样本内试验台账，不再跑 LEAN。";
    }
    return "联合 stationary bootstrap 保留试验之间的相关。Hansen SPA_c 不能拒绝「没有优于现金的模型」则不能进入 VALIDATED。至少 2 条可区分试验、252 个共同交易日；超过 64 条拒绝截断。";
  }, [items.length, latest]);

  const create = useMutation({
    mutationFn: () => {
      if (!versionId) throw new Error("没有可验证的策略版本");
      return api.createSpa({
        strategy_version_id: versionId,
        backtest_id: latest?.id,
        n_boot: 1000,
        alpha: 0.05,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["validation-runs"] });
      toast("Reality Check 已提交", "ok");
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <label className="block max-w-sm space-y-1 text-[11px] text-as-muted">
        策略
        <select
          className={selectClass}
          value={selected?.id ?? ""}
          onChange={(e) => setStrategyId(e.target.value)}
        >
          {items.length ? (
            items.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name} · {row.status}
              </option>
            ))
          ) : (
            <option value="">还没有策略</option>
          )}
        </select>
      </label>
      <p className="text-[11px] leading-relaxed text-as-muted">{hint}</p>
      <Button type="submit" disabled={!versionId || !latest || create.isPending}>
        {create.isPending ? "提交中…" : "运行 Reality Check"}
      </Button>
    </form>
  );
}
