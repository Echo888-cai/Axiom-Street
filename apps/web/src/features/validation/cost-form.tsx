"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";

const selectClass =
  "h-9 w-full rounded-lg border border-as-border bg-as-bg px-3 text-sm text-as-text outline-none focus:border-as-primary/40 focus-visible:ring-2 focus-visible:ring-as-primary/20";

function readsSlippage(code: string | undefined): boolean {
  if (!code) return false;
  return (
    code.includes('GetParameter("slippage_bps")') || code.includes("GetParameter('slippage_bps')")
  );
}

function parseCosts(raw: string): number[] {
  const nums = raw
    .split(/[,\s]+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => Number(part));
  if (nums.some((n) => !Number.isFinite(n) || n < 0)) {
    throw new Error("成本必须是 ≥ 0 的数字，单位 bps，用逗号分隔。");
  }
  const unique = [...new Set(nums)].sort((a, b) => a - b);
  if (unique.length < 3 || unique.length > 12) {
    throw new Error("成本网格需要 3–12 个互异非负 bps。");
  }
  if (!unique.includes(0)) {
    throw new Error("成本网格必须包含 0 bps。");
  }
  return unique;
}

export function CostScanForm() {
  const qc = useQueryClient();
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.listStrategies });
  const [strategyId, setStrategyId] = useState("");
  const [start, setStart] = useState("2018-01-01");
  const [end, setEnd] = useState("2020-12-31");
  const [costsRaw, setCostsRaw] = useState("0, 1, 2, 5, 10, 20, 50");
  const [realistic, setRealistic] = useState(5);

  const items = strategies.data ?? [];
  const selected = items.find((row) => row.id === strategyId) ?? items[0];
  const versionId = selected?.latest_version?.id;
  const code = selected?.latest_version?.code;
  const hasSlippage = readsSlippage(code);

  const backtests = useQuery({
    queryKey: ["backtests", selected?.id, "COMPLETED"],
    queryFn: () => api.listBacktests({ strategy_id: selected?.id, status: "COMPLETED" }),
    enabled: Boolean(selected?.id),
  });
  const latest = backtests.data?.[0];

  useEffect(() => {
    if (!selected && items[0]) setStrategyId(items[0].id);
  }, [items, selected]);

  useEffect(() => {
    if (!latest) return;
    setStart(latest.start_date.slice(0, 10));
    setEnd(latest.end_date.slice(0, 10));
  }, [latest?.id]);

  const hint = useMemo(() => {
    if (!items.length) return "先建一条策略。";
    if (!hasSlippage) {
      return "该版本没有读取 LEAN 参数 slippage_bps。成本扫描必须能改滑点，否则净值不变。请先提交新版本。";
    }
    if (!latest) {
      return "先对该版本跑完一次全样本回测。扫描借用那次回测的标的池与快照。";
    }
    return "单边成本全部计入 slippage_bps，fee_usd 置 0。临界成本不高于真实单边成本则判死。默认真实成本 5 bps 与项目填单约定一致。";
  }, [items.length, hasSlippage, latest]);

  const create = useMutation({
    mutationFn: () => {
      if (!versionId) throw new Error("没有可扫描的策略版本");
      const costs_bps = parseCosts(costsRaw);
      return api.createCostScan({
        strategy_version_id: versionId,
        backtest_id: latest?.id,
        start_date: start,
        end_date: end,
        costs_bps,
        realistic_one_way_bps: realistic,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["validation-runs"] });
      qc.invalidateQueries({ queryKey: ["backtests"] });
      toast("成本扫描已提交", "ok");
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
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className="space-y-1 text-[11px] text-as-muted">
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
        <label className="space-y-1 text-[11px] text-as-muted sm:col-span-2">
          单边成本网格（bps）
          <Input
            value={costsRaw}
            onChange={(e) => setCostsRaw(e.target.value)}
            placeholder="0, 1, 2, 5, 10, 20, 50"
          />
        </label>
        <label className="space-y-1 text-[11px] text-as-muted">
          开始
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label className="space-y-1 text-[11px] text-as-muted">
          结束
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <label className="space-y-1 text-[11px] text-as-muted">
          真实单边成本（bps）
          <Input
            type="number"
            min={0}
            max={200}
            step={0.5}
            value={realistic}
            onChange={(e) => setRealistic(Number(e.target.value) || 0)}
          />
        </label>
      </div>
      <p className="text-[11px] leading-relaxed text-as-muted">{hint}</p>
      <Button type="submit" disabled={!versionId || !latest || !hasSlippage || create.isPending}>
        {create.isPending ? "提交中…" : "运行成本扫描"}
      </Button>
    </form>
  );
}
