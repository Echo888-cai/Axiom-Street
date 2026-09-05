"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";

const selectClass =
  "h-9 w-full rounded-lg border border-as-border bg-as-bg px-3 text-sm text-as-text outline-none focus:border-as-primary/40 focus:ring-2 focus-visible:ring-as-primary/20";

function spanYears(start: string, end: string): number {
  const from = new Date(start).getTime();
  const to = new Date(end).getTime();
  if (Number.isNaN(from) || Number.isNaN(to) || to <= from) return 0;
  return (to - from) / (365.25 * 24 * 60 * 60 * 1000);
}

export function WalkForwardForm() {
  const qc = useQueryClient();
  const strategies = useQuery({
    queryKey: ["strategies"],
    queryFn: api.listStrategies,
  });
  const [strategyId, setStrategyId] = useState("");
  const [start, setStart] = useState("2018-01-01");
  const [end, setEnd] = useState("2020-12-31");
  const [trainYears, setTrainYears] = useState(1);
  const [testYears, setTestYears] = useState(1);
  const [mode, setMode] = useState<"rolling" | "anchored">("rolling");
  const [embargoDays, setEmbargoDays] = useState(1);

  const items = strategies.data ?? [];
  const selected = items.find((row) => row.id === strategyId) ?? items[0];
  const versionId = selected?.latest_version?.id;

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
    const years = spanYears(latest.start_date, latest.end_date);
    setTrainYears(years >= 4 ? 3 : 1);
    setTestYears(1);
  }, [latest]);

  const hint = useMemo(() => {
    if (!items.length) return "先建一条策略。";
    if (!latest)
      return "先对该版本跑完一次全样本回测。Walk-forward 借用那次回测的标的池与快照，不会猜测 SPY。";
    const years = spanYears(start, end);
    if (years < trainYears + testYears + 0.9) {
      return "当前区间切不出两折完整样本外。缩短训练年数，或把回测历史拉长。";
    }
    return `将按 ${mode === "rolling" ? "滚动" : "锚定"} 窗口，从已完成回测的快照上重跑每一折。`;
  }, [items.length, latest, start, end, trainYears, testYears, mode]);

  const create = useMutation({
    mutationFn: () => {
      if (!versionId) throw new Error("没有可验证的策略版本");
      return api.createWalkForward({
        strategy_version_id: versionId,
        backtest_id: latest?.id,
        start_date: start,
        end_date: end,
        train_years: trainYears,
        test_years: testYears,
        mode,
        embargo_days: embargoDays,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["validation-runs"] });
      toast("Walk-forward 已提交", "ok");
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
        <label className="space-y-1 text-[11px] text-as-muted">
          模式
          <select
            className={selectClass}
            value={mode}
            onChange={(e) => setMode(e.target.value as "rolling" | "anchored")}
          >
            <option value="rolling">滚动（固定样本内）</option>
            <option value="anchored">锚定（扩张样本内）</option>
          </select>
        </label>
        <label className="space-y-1 text-[11px] text-as-muted">
          隔离天数
          <Input
            type="number"
            min={1}
            max={30}
            value={embargoDays}
            onChange={(e) => setEmbargoDays(Number(e.target.value) || 1)}
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
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1 text-[11px] text-as-muted">
            训练（年）
            <Input
              type="number"
              min={1}
              max={20}
              value={trainYears}
              onChange={(e) => setTrainYears(Number(e.target.value) || 1)}
            />
          </label>
          <label className="space-y-1 text-[11px] text-as-muted">
            测试（年）
            <Input
              type="number"
              min={1}
              max={10}
              value={testYears}
              onChange={(e) => setTestYears(Number(e.target.value) || 1)}
            />
          </label>
        </div>
      </div>
      <p className="text-[11px] leading-relaxed text-as-muted">{hint}</p>
      <Button
        type="submit"
        disabled={!versionId || !latest || create.isPending}
      >
        {create.isPending ? "提交中…" : "运行 Walk-forward"}
      </Button>
    </form>
  );
}
