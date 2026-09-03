"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Beaker } from "lucide-react";
import { api, type ValidationRun } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { PboScanForm } from "@/features/experiments/pbo-scan-form";

function isInflight(row: ValidationRun): boolean {
  return row.status === "QUEUED" || row.status === "RUNNING";
}

function conclusion(row: ValidationRun) {
  if (row.status === "QUEUED" || row.status === "RUNNING") {
    return { tone: "blue" as const, label: row.progress_step || row.status };
  }
  if (row.error) return { tone: "red" as const, label: "失败" };
  return row.passed
    ? { tone: "green" as const, label: "PBO ≤ 0.5" }
    : { tone: "amber" as const, label: "PBO > 0.5" };
}

type ConfigRow = {
  lookback?: number;
  backtest_id?: string;
  sharpe?: number | null;
};

function asConfigs(result: Record<string, unknown>): ConfigRow[] {
  return Array.isArray(result.configs) ? (result.configs as ConfigRow[]) : [];
}

function PboReport({ run }: { run: ValidationRun }) {
  const pbo = typeof run.result.pbo === "number" ? run.result.pbo : null;
  const nSlices = typeof run.result.n_slices === "number" ? run.result.n_slices : null;
  const nCombos =
    typeof run.result.n_combinations === "number" ? run.result.n_combinations : null;
  const nObs = typeof run.result.n_obs_aligned === "number" ? run.result.n_obs_aligned : null;
  const configs = asConfigs(run.result);
  const maxAbs = Math.max(0.5, ...configs.map((row) => Math.abs(Number(row.sharpe) || 0)));

  return (
    <Card>
      <CardHeader
        title="最近一次 CSCV"
        hint={
          <p className="text-xs text-as-muted">
            样本内最优配置在样本外落入中位数以下的比例。PBO &gt; 0.5 不能进入 VALIDATED。
          </p>
        }
      />
      <div className="mb-6 flex flex-wrap items-end gap-6">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-as-muted">PBO</div>
          <div
            className={`mt-1 text-3xl font-semibold tabular-nums ${
              pbo != null && pbo > 0.5 ? "text-as-negative" : "text-as-text"
            }`}
          >
            {pbo == null ? "—" : pbo.toFixed(2)}
          </div>
        </div>
        <p className="max-w-xl text-sm leading-relaxed text-as-muted">
          {nSlices != null ? `${nSlices} 个切片` : "切片未记录"}
          {nCombos != null ? ` · ${nCombos} 种划分` : ""}
          {nObs != null ? ` · ${nObs} 个共同交易日` : ""}
        </p>
      </div>
      {configs.length ? (
        <div className="space-y-2">
          {configs.map((row) => {
            const sharpe = Number(row.sharpe) || 0;
            const width = Math.max(8, Math.min(100, (Math.abs(sharpe) / maxAbs) * 100));
            return (
              <div
                key={`${row.lookback}-${row.backtest_id}`}
                className="grid gap-2 sm:grid-cols-[7.5rem_1fr] sm:items-center"
              >
                <div className="text-[11px] text-as-muted">
                  <div className="font-medium tabular-nums text-as-text">
                    lookback {row.lookback ?? "—"}
                  </div>
                  {row.backtest_id ? (
                    <Link
                      href={`/backtests/${row.backtest_id}`}
                      className="text-as-primary hover:underline"
                    >
                      {row.backtest_id.slice(0, 8)}…
                    </Link>
                  ) : null}
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-2 flex-1 rounded-full bg-as-secondary">
                    <div
                      className={`h-2 rounded-full ${sharpe < 0 ? "bg-as-negative" : "bg-as-primary"}`}
                      style={{ width: `${width}%` }}
                    />
                  </div>
                  <span className="w-14 shrink-0 text-right text-xs tabular-nums text-as-text">
                    {row.sharpe == null ? "—" : sharpe.toFixed(2)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </Card>
  );
}

export function ExperimentsDesk() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["pbo-runs"],
    queryFn: () => api.listValidation({ kind: "PBO" }),
    refetchInterval: (query) => {
      const rows = query.state.data?.items ?? [];
      return rows.some(isInflight) ? 2000 : false;
    },
  });

  const items = data?.items ?? [];
  const latest = items[0];

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        title="实验"
        description="参数扫描写入试验台账，并计算 PBO。敏感性与成本闸门在验证页。这不是找赢家的快捷方式：PBO > 0.5 的版本不能标成已验证。"
      />

      <Card>
        <CardHeader
          title="lookback 扫描"
          hint={
            <p className="text-xs text-as-muted">
              目前只扫 LEAN 参数 lookback。每个格子一次真实回测。完整闸门在{" "}
              <Link href="/validation" className="text-as-primary hover:underline">
                验证
              </Link>
              。
            </p>
          }
        />
        <PboScanForm />
      </Card>

      {latest && (latest.status === "COMPLETED" || latest.error) ? <PboReport run={latest} /> : null}

      {isLoading ? (
        <Card className="h-40 animate-pulse bg-as-secondary" />
      ) : error ? (
        <Card>
          <EmptyState title="API 未连接" description="请先启动 FastAPI 服务（端口 8000）。" />
        </Card>
      ) : !items.length ? (
        <Card className="min-h-[240px]">
          <EmptyState
            icon={Beaker}
            title="还没有参数扫描"
            description="对读取 lookback 的策略提交网格。系统不会用一次回测假装算出 PBO。"
          />
        </Card>
      ) : (
        <Card className="p-0">
          <div className="border-b border-as-border px-5 py-3 text-sm font-medium">扫描记录</div>
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-as-muted">
              <tr className="border-b border-as-border">
                <th className="px-5 py-2 font-medium">状态</th>
                <th className="px-5 py-2 font-medium">结论</th>
                <th className="px-5 py-2 font-medium">PBO</th>
                <th className="px-5 py-2 font-medium">网格</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => {
                const badge = conclusion(row);
                const pbo = typeof row.result.pbo === "number" ? row.result.pbo : null;
                const values = Array.isArray(row.params.values)
                  ? (row.params.values as number[]).join(", ")
                  : "—";
                return (
                  <tr key={row.id} className="border-b border-as-border last:border-0">
                    <td className="px-5 py-3 text-xs text-as-muted">{row.status}</td>
                    <td className="px-5 py-3">
                      <Badge tone={badge.tone}>{badge.label}</Badge>
                      {row.error?.message ? (
                        <p className="mt-1 text-xs text-as-muted">{row.error.message}</p>
                      ) : null}
                    </td>
                    <td className="px-5 py-3 tabular-nums text-as-muted">
                      {pbo == null ? "—" : pbo.toFixed(2)}
                    </td>
                    <td className="px-5 py-3 tabular-nums text-as-muted">{values}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
