"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BadgeCheck } from "lucide-react";
import { api, type ValidationRun } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { EquityCurve } from "@/components/charts/equity-curve";
import { formatPct } from "@/lib/utils";
import { FoldSharpeBars } from "@/features/validation/fold-sharpe-bars";
import { WalkForwardForm } from "@/features/validation/walk-forward-form";
import { SensitivityForm } from "@/features/validation/sensitivity-form";
import { CostScanForm } from "@/features/validation/cost-form";
import { BootstrapForm } from "@/features/validation/bootstrap-form";
import { CostAlphaBars, SharpeSurfaceBars } from "@/features/validation/surface-bars";

function isInflight(row: ValidationRun): boolean {
  return row.status === "QUEUED" || row.status === "RUNNING";
}

function conclusion(row: ValidationRun) {
  if (row.status === "QUEUED" || row.status === "RUNNING") {
    return { tone: "blue" as const, label: row.progress_step || row.status };
  }
  if (row.error) return { tone: "red" as const, label: "失败" };
  if (row.kind === "DSR") {
    return row.passed
      ? { tone: "green" as const, label: "通过 95%" }
      : { tone: "amber" as const, label: "未过线" };
  }
  if (row.kind === "PBO") {
    return row.passed
      ? { tone: "green" as const, label: "PBO ≤ 0.5" }
      : { tone: "amber" as const, label: "PBO > 0.5" };
  }
  if (row.kind === "SENSITIVITY") {
    return row.passed
      ? { tone: "green" as const, label: "高原" }
      : { tone: "amber" as const, label: "孤峰" };
  }
  if (row.kind === "COST") {
    return row.passed
      ? { tone: "green" as const, label: "成本可承受" }
      : { tone: "amber" as const, label: "临界成本过低" };
  }
  if (row.kind === "BOOTSTRAP") {
    return row.passed
      ? { tone: "green" as const, label: "Sharpe CI > 0" }
      : { tone: "amber" as const, label: "区间跨零" };
  }
  return row.passed
    ? { tone: "green" as const, label: "通过" }
    : { tone: "amber" as const, label: "未通过" };
}

function asFolds(result: Record<string, unknown>): Array<Record<string, unknown>> {
  return Array.isArray(result.folds) ? (result.folds as Array<Record<string, unknown>>) : [];
}

function asEquity(result: Record<string, unknown>): Array<{ time: string; strategy: number }> {
  const raw = Array.isArray(result.oos_equity) ? result.oos_equity : [];
  return raw
    .map((point) => {
      const row = point as { ts?: string; strategy_value?: number };
      if (!row.ts || typeof row.strategy_value !== "number") return null;
      return { time: String(row.ts).slice(0, 10), strategy: row.strategy_value };
    })
    .filter((point): point is { time: string; strategy: number } => point != null);
}

function WalkForwardReport({ run }: { run: ValidationRun }) {
  const folds = asFolds(run.result);
  const equity = asEquity(run.result);
  const combined =
    typeof run.result.combined_oos_sharpe === "number" ? run.result.combined_oos_sharpe : null;
  const reason = typeof run.result.reason === "string" ? run.result.reason : null;
  return (
    <Card>
      <CardHeader
        title="最近一次 Walk-forward"
        hint={
          <p className="text-xs text-as-muted">
            {run.params.mode === "anchored" ? "锚定" : "滚动"} · 训练{" "}
            {String(run.params.train_years ?? "—")} 年 / 测试 {String(run.params.test_years ?? "—")} 年
          </p>
        }
      />
      {reason ? <p className="mb-4 text-sm leading-relaxed text-as-text">{reason}</p> : null}
      {combined != null ? (
        <p className="mb-4 text-xs text-as-muted">
          拼接样本外 Sharpe{" "}
          <span className="tabular-nums text-as-text">{combined.toFixed(2)}</span>
          {run.result.overfit_collapse === true ? " · 判定为过拟合塌缩" : ""}
        </p>
      ) : null}
      {folds.length ? <FoldSharpeBars folds={folds} /> : null}
      {equity.length ? (
        <div className="mt-6">
          <h4 className="mb-2 text-xs font-medium text-as-muted">拼接样本外净值</h4>
          <EquityCurve data={equity} height={220} />
        </div>
      ) : null}
    </Card>
  );
}

function asPoints(result: Record<string, unknown>): Array<Record<string, unknown>> {
  return Array.isArray(result.points) ? (result.points as Array<Record<string, unknown>>) : [];
}

function SensitivityReport({ run }: { run: ValidationRun }) {
  const reason = typeof run.result.reason === "string" ? run.result.reason : null;
  const shape = typeof run.result.shape === "string" ? run.result.shape : null;
  const peakSharpe =
    typeof run.result.peak_sharpe === "number" ? run.result.peak_sharpe : null;
  const width = typeof run.result.plateau_width === "number" ? run.result.plateau_width : null;
  const points = asPoints(run.result);
  return (
    <Card>
      <CardHeader
        title="最近一次参数敏感性"
        hint={
          <p className="text-xs text-as-muted">
            最优点周围 Sharpe 是否形成高原。孤峰是过拟合特征，不能进入 VALIDATED。
          </p>
        }
      />
      {reason ? <p className="mb-4 text-sm leading-relaxed text-as-text">{reason}</p> : null}
      <p className="mb-4 text-xs text-as-muted">
        {shape === "plateau" ? "高原" : shape === "knife_edge" ? "孤峰" : "形态未记录"}
        {peakSharpe != null ? ` · 峰值 Sharpe ${peakSharpe.toFixed(2)}` : ""}
        {width != null ? ` · 带宽 ${width} 点` : ""}
      </p>
      {points.length ? (
        <SharpeSurfaceBars
          points={points.map((row) => ({
            value: typeof row.value === "number" ? row.value : undefined,
            sharpe: typeof row.sharpe === "number" ? row.sharpe : null,
            backtest_id: typeof row.backtest_id === "string" ? row.backtest_id : null,
            on_plateau: row.on_plateau === true,
            is_peak: row.is_peak === true,
          }))}
        />
      ) : null}
    </Card>
  );
}

function asInterval(raw: unknown): { observed: number; low: number; high: number } | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as { observed?: unknown; low?: unknown; high?: unknown };
  if (
    typeof row.observed !== "number" ||
    typeof row.low !== "number" ||
    typeof row.high !== "number"
  ) {
    return null;
  }
  return { observed: row.observed, low: row.low, high: row.high };
}

function IntervalRow({
  label,
  interval,
  format,
}: {
  label: string;
  interval: { observed: number; low: number; high: number };
  format: (n: number) => string;
}) {
  const span = interval.high - interval.low;
  const absBound = Math.max(Math.abs(interval.low), Math.abs(interval.high), Math.abs(interval.observed), 1e-9);
  const left = ((interval.low + absBound) / (2 * absBound)) * 100;
  const width = Math.max(4, (span / (2 * absBound)) * 100);
  const obsLeft = ((interval.observed + absBound) / (2 * absBound)) * 100;
  const crosses = interval.low <= 0 && interval.high >= 0;
  return (
    <div className="grid gap-2 sm:grid-cols-[6.5rem_1fr_9rem] sm:items-center">
      <div className="text-[11px] text-as-muted">{label}</div>
      <div className="relative h-2 rounded-full bg-as-secondary">
        <div
          className={`absolute top-0 h-2 rounded-full ${crosses ? "bg-as-negative/70" : "bg-as-primary"}`}
          style={{ left: `${left}%`, width: `${width}%` }}
        />
        <div
          className="absolute top-[-2px] h-3 w-0.5 bg-as-text"
          style={{ left: `${obsLeft}%` }}
          title={`观测 ${format(interval.observed)}`}
        />
      </div>
      <div className="tabular-nums text-[11px] text-as-muted">
        {format(interval.observed)} [{format(interval.low)}, {format(interval.high)}]
      </div>
    </div>
  );
}

function BootstrapReport({ run }: { run: ValidationRun }) {
  const reason = typeof run.result.reason === "string" ? run.result.reason : null;
  const sharpe = asInterval(run.result.sharpe);
  const cagr = asInterval(run.result.cagr);
  const maxDd = asInterval(run.result.max_drawdown);
  const nBoot = typeof run.result.n_boot === "number" ? run.result.n_boot : null;
  const meanBlock =
    typeof run.result.mean_block_length === "number" ? run.result.mean_block_length : null;
  const level =
    typeof run.result.confidence_level === "number" ? run.result.confidence_level : 0.95;
  return (
    <Card>
      <CardHeader
        title="最近一次 Bootstrap"
        hint={
          <p className="text-xs text-as-muted">
            Stationary bootstrap {level * 100}% 分位区间。Sharpe 下界 ≤ 0 不能进入 VALIDATED。
            {nBoot != null ? ` · ${nBoot} 次重抽样` : ""}
            {meanBlock != null ? ` · 平均块长 ${meanBlock.toFixed(1)}` : ""}
          </p>
        }
      />
      {reason ? <p className="mb-4 text-sm leading-relaxed text-as-text">{reason}</p> : null}
      <div className="space-y-3">
        {sharpe ? (
          <IntervalRow label="Sharpe" interval={sharpe} format={(n) => n.toFixed(2)} />
        ) : null}
        {cagr ? (
          <IntervalRow label="CAGR" interval={cagr} format={(n) => formatPct(n)} />
        ) : null}
        {maxDd ? (
          <IntervalRow label="MaxDD" interval={maxDd} format={(n) => formatPct(n)} />
        ) : null}
      </div>
    </Card>
  );
}

function CostReport({ run }: { run: ValidationRun }) {
  const conclusionText =
    typeof run.result.conclusion === "string" ? run.result.conclusion : null;
  const reason = typeof run.result.reason === "string" ? run.result.reason : null;
  const breakeven =
    typeof run.result.breakeven_bps === "number" ? run.result.breakeven_bps : null;
  const realistic =
    typeof run.result.realistic_one_way_bps === "number"
      ? run.result.realistic_one_way_bps
      : null;
  const points = asPoints(run.result);
  return (
    <Card>
      <CardHeader
        title="最近一次成本敏感性"
        hint={
          <p className="text-xs text-as-muted">
            alpha_capm 归零的单边成本。不高于真实成本则策略判死。
          </p>
        }
      />
      {conclusionText ? (
        <p className="mb-2 text-sm leading-relaxed text-as-text">{conclusionText}</p>
      ) : null}
      {reason ? <p className="mb-4 text-xs leading-relaxed text-as-muted">{reason}</p> : null}
      <p className="mb-4 text-xs text-as-muted">
        临界{" "}
        <span className="tabular-nums text-as-text">
          {breakeven == null ? "> 网格上限" : `${breakeven.toFixed(2)} bps`}
        </span>
        {realistic != null ? ` · 真实 ${realistic} bps` : ""}
      </p>
      {points.length ? (
        <CostAlphaBars
          points={points.map((row) => ({
            cost_bps: typeof row.cost_bps === "number" ? row.cost_bps : undefined,
            alpha_capm: typeof row.alpha_capm === "number" ? row.alpha_capm : null,
            backtest_id: typeof row.backtest_id === "string" ? row.backtest_id : null,
          }))}
          realisticBps={realistic}
        />
      ) : null}
    </Card>
  );
}

export function ValidationDesk() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["validation-runs"],
    queryFn: () => api.listValidation(),
    refetchInterval: (query) => {
      const rows = query.state.data?.items ?? [];
      return rows.some(isInflight) ? 2000 : false;
    },
  });

  const gates = data?.gates;
  const items = data?.items ?? [];
  const latestWalk = items.find((row) => row.kind === "WALK_FORWARD");
  const latestSens = items.find((row) => row.kind === "SENSITIVITY");
  const latestCost = items.find((row) => row.kind === "COST");
  const latestBoot = items.find((row) => row.kind === "BOOTSTRAP");

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        title="验证"
        description="统计验证是进入 VALIDATED 的唯一路径。客户端不能把策略标成已验证。"
      />

      <Card>
        <p className="text-sm text-as-text">{gates?.note || "正在读取验证闸门…"}</p>
        <dl className="mt-4 grid gap-3 text-xs text-as-muted sm:grid-cols-3">
          <div>
            <dt className="text-[11px] uppercase tracking-wide">已实现</dt>
            <dd className="mt-1 text-as-text">{(gates?.available || ["DSR", "WALK_FORWARD", "PBO", "SENSITIVITY", "COST", "BOOTSTRAP"]).join(" · ")}</dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide">VALIDATED 需要</dt>
            <dd className="mt-1 text-as-text">
              {(gates?.validated_requires || ["WALK_FORWARD", "DSR", "PBO", "SENSITIVITY", "COST", "BOOTSTRAP"]).join(" · ")}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide">尚未接入</dt>
            <dd className="mt-1">{(gates?.missing || []).join(" · ") || "—"}</dd>
          </div>
        </dl>
      </Card>

      <Card>
        <CardHeader
          title="Walk-forward"
          hint={<p className="text-xs text-as-muted">每折一次完整 LEAN 运行，样本外拼接后评分。过拟合塌缩不能进入 VALIDATED。参数扫描在 <Link href="/experiments" className="text-as-primary hover:underline">实验</Link>。</p>}
        />
        <WalkForwardForm />
      </Card>

      {latestWalk && (latestWalk.status === "COMPLETED" || latestWalk.error) ? (
        <WalkForwardReport run={latestWalk} />
      ) : null}

      <Card>
        <CardHeader
          title="参数敏感性"
          hint={
            <p className="text-xs text-as-muted">
              扰动 lookback，判断 Sharpe 响应是高原还是孤峰。PBO 参数扫描仍在{" "}
              <Link href="/experiments" className="text-as-primary hover:underline">
                实验
              </Link>
              。
            </p>
          }
        />
        <SensitivityForm />
      </Card>

      {latestSens && (latestSens.status === "COMPLETED" || latestSens.error) ? (
        <SensitivityReport run={latestSens} />
      ) : null}

      <Card>
        <CardHeader
          title="成本敏感性"
          hint={
            <p className="text-xs text-as-muted">
              逐步提高单边滑点，求 alpha_capm 归零的临界成本。
            </p>
          }
        />
        <CostScanForm />
      </Card>

      {latestCost && (latestCost.status === "COMPLETED" || latestCost.error) ? (
        <CostReport run={latestCost} />
      ) : null}

      <Card>
        <CardHeader
          title="Bootstrap 置信区间"
          hint={
            <p className="text-xs text-as-muted">
              对已完成回测的日收益做 stationary bootstrap。区间跨零则无统计显著性。
            </p>
          }
        />
        <BootstrapForm />
      </Card>

      {latestBoot && (latestBoot.status === "COMPLETED" || latestBoot.error) ? (
        <BootstrapReport run={latestBoot} />
      ) : null}

      {isLoading ? (
        <Card className="h-40 animate-pulse bg-as-secondary" />
      ) : error ? (
        <Card>
          <EmptyState title="API 未连接" description="请先启动 FastAPI 服务（端口 8000）。" />
        </Card>
      ) : !items.length ? (
        <Card className="min-h-[240px]">
          <EmptyState
            icon={BadgeCheck}
            title="还没有验证记录"
            description="跑完一次回测后会写下 Deflated Sharpe 与 Bootstrap。Walk-forward、DSR、PBO、敏感性高原、成本与 Sharpe 区间都通过后，系统才会把策略标成已验证。"
          />
        </Card>
      ) : (
        <Card className="p-0">
          <div className="border-b border-as-border px-5 py-3 text-sm font-medium">验证运行</div>
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-as-muted">
              <tr className="border-b border-as-border">
                <th className="px-5 py-2 font-medium">类型</th>
                <th className="px-5 py-2 font-medium">状态</th>
                <th className="px-5 py-2 font-medium">结论</th>
                <th className="px-5 py-2 font-medium">摘要</th>
                <th className="px-5 py-2 font-medium">回测</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => {
                const badge = conclusion(row);
                const pbo = typeof row.result.pbo === "number" ? row.result.pbo : null;
                const dsr = typeof row.result.dsr === "number" ? row.result.dsr : null;
                const n = typeof row.result.n_trials === "number" ? row.result.n_trials : null;
                const oos =
                  typeof row.result.combined_oos_sharpe === "number"
                    ? row.result.combined_oos_sharpe
                    : null;
                const shape = typeof row.result.shape === "string" ? row.result.shape : null;
                const breakeven =
                  typeof row.result.breakeven_bps === "number" ? row.result.breakeven_bps : null;
                const sharpeCi = asInterval(row.result.sharpe);
                const summary =
                  row.kind === "DSR"
                    ? `${dsr == null ? "—" : formatPct(dsr)}${n != null ? ` · N=${n}` : ""}`
                    : row.kind === "PBO"
                      ? pbo == null
                        ? "—"
                        : `PBO ${pbo.toFixed(2)}`
                      : row.kind === "SENSITIVITY"
                        ? shape == null
                          ? "—"
                          : shape === "plateau"
                            ? "高原"
                            : "孤峰"
                        : row.kind === "COST"
                          ? breakeven == null && row.passed
                            ? "> 网格上限"
                            : breakeven == null
                              ? "—"
                              : `${breakeven.toFixed(1)} bps`
                          : row.kind === "BOOTSTRAP"
                            ? sharpeCi
                              ? `${sharpeCi.observed.toFixed(2)} [${sharpeCi.low.toFixed(2)}, ${sharpeCi.high.toFixed(2)}]`
                              : "—"
                            : oos == null
                              ? "—"
                              : `OOS Sharpe ${oos.toFixed(2)}`;
                return (
                  <tr key={row.id} className="border-b border-as-border last:border-0">
                    <td className="px-5 py-3 font-medium">{row.kind}</td>
                    <td className="px-5 py-3 text-xs text-as-muted">{row.status}</td>
                    <td className="px-5 py-3">
                      <Badge tone={badge.tone}>{badge.label}</Badge>
                      {row.error?.message ? (
                        <p className="mt-1 text-xs text-as-muted">{row.error.message}</p>
                      ) : null}
                    </td>
                    <td className="px-5 py-3 tabular-nums text-as-muted">{summary}</td>
                    <td className="px-5 py-3">
                      {row.backtest_id ? (
                        <Link
                          href={`/backtests/${row.backtest_id}`}
                          className="text-as-primary hover:underline"
                        >
                          {row.backtest_id.slice(0, 8)}…
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
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
