"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";

const selectClass =
  "h-9 w-full rounded-lg border border-as-border bg-as-bg px-3 text-sm text-as-text outline-none focus:border-as-primary/40 focus-visible:ring-2 focus-visible:ring-as-primary/20";

function readsLookback(code: string | undefined): boolean {
  if (!code) return false;
  return (
    code.includes('GetParameter("lookback")') ||
    code.includes("GetParameter('lookback')")
  );
}

function parseValues(raw: string): number[] {
  const nums = raw
    .split(/[,\s]+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => Number(part));
  if (nums.some((n) => !Number.isInteger(n) || n < 2)) {
    throw new Error("lookback 必须是 ≥ 2 的整数，用逗号分隔。");
  }
  const unique = [...new Set(nums)].sort((a, b) => a - b);
  if (unique.length < 3 || unique.length > 12) {
    throw new Error("敏感性网格需要 3–12 个互异正整数。");
  }
  return unique;
}

export function SensitivityForm() {
  const qc = useQueryClient();
  const strategies = useQuery({
    queryKey: ["strategies"],
    queryFn: api.listStrategies,
  });
  const [strategyId, setStrategyId] = useState("");
  const [start, setStart] = useState("2018-01-01");
  const [end, setEnd] = useState("2020-12-31");
  const [valuesRaw, setValuesRaw] = useState("100, 150, 200, 250, 300");

  const items = strategies.data ?? [];
  const selected = items.find((row) => row.id === strategyId) ?? items[0];
  const versionId = selected?.latest_version?.id;
  const code = selected?.latest_version?.code;
  const hasLookback = readsLookback(code);

  const backtests = useQuery({
    queryKey: ["backtests", selected?.id, "COMPLETED"],
    queryFn: () =>
      api.listBacktests({ strategy_id: selected?.id, status: "COMPLETED" }),
    enabled: Boolean(selected?.id),
  });
  const latest = backtests.data?.[0];

  useEffect(() => {
    if (!latest) return;
    setStart(latest.start_date.slice(0, 10));
    setEnd(latest.end_date.slice(0, 10));
  }, [latest]);

  const hint = useMemo(() => {
    if (!items.length) return "先建一条策略。";
    if (!hasLookback) {
      return "该版本没有读取 LEAN 参数 lookback。扰动一个策略读不到的字段会得到相同净值。请先提交新版本。";
    }
    if (!latest) {
      return "先对该版本跑完一次全样本回测。扫描借用那次回测的标的池与快照。";
    }
    return "每个参数点是一次完整 LEAN 回测。孤峰不能进入 VALIDATED；高原才算稳健。";
  }, [items.length, hasLookback, latest]);

  const create = useMutation({
    mutationFn: () => {
      if (!versionId) throw new Error("没有可扫描的策略版本");
      const values = parseValues(valuesRaw);
      return api.createSensitivityScan({
        strategy_version_id: versionId,
        backtest_id: latest?.id,
        start_date: start,
        end_date: end,
        values,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["validation-runs"] });
      qc.invalidateQueries({ queryKey: ["backtests"] });
      toast("敏感性扫描已提交", "ok");
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
          lookback 网格
          <Input
            value={valuesRaw}
            onChange={(e) => setValuesRaw(e.target.value)}
            placeholder="100, 150, 200, 250, 300"
          />
        </label>
        <label className="space-y-1 text-[11px] text-as-muted">
          开始
          <Input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label className="space-y-1 text-[11px] text-as-muted">
          结束
          <Input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
      </div>
      <p className="text-[11px] leading-relaxed text-as-muted">{hint}</p>
      <Button
        type="submit"
        disabled={!versionId || !latest || !hasLookback || create.isPending}
      >
        {create.isPending ? "提交中…" : "运行敏感性扫描"}
      </Button>
    </form>
  );
}
