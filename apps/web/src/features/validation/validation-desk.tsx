"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BadgeCheck } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { formatPct } from "@/lib/utils";
import { WalkForwardForm } from "@/features/validation/walk-forward-form";
import { SensitivityForm } from "@/features/validation/sensitivity-form";
import { CostScanForm } from "@/features/validation/cost-form";
import { BootstrapForm } from "@/features/validation/bootstrap-form";
import { RegimeForm } from "@/features/validation/regime-form";
import { SpaForm } from "@/features/validation/spa-form";
import { isInflight, conclusion } from "./validation-status";
import { WalkForwardReport } from "./reports/walk-forward-report";
import { SensitivityReport } from "./reports/sensitivity-report";
import { asInterval, BootstrapReport } from "./reports/bootstrap-report";
import { RegimeReport } from "./reports/regime-report";
import { SpaReport } from "./reports/spa-report";
import { CostReport } from "./reports/cost-report";

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
  const latestRegime = items.find((row) => row.kind === "REGIME");
  const latestSpa = items.find((row) => row.kind === "SPA");

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        title="稳健性验证"
        description="一个漂亮的结果，还需要经得住样本外、成本与市场变化的检验。"
      />

      <Card>
        <p className="text-sm text-as-text">
          {gates?.note ||
            (error ? "连接研究服务后查看验证要求。" : "正在读取验证闸门…")}
        </p>
        <dl className="mt-4 grid gap-3 text-xs text-as-muted sm:grid-cols-3">
          <div>
            <dt className="text-[11px] uppercase tracking-wide">已实现</dt>
            <dd className="mt-1 text-as-text">
              {(
                gates?.available || [
                  "DSR",
                  "WALK_FORWARD",
                  "PBO",
                  "SENSITIVITY",
                  "COST",
                  "BOOTSTRAP",
                  "REGIME",
                  "SPA",
                ]
              ).join(" · ")}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide">
              VALIDATED 需要
            </dt>
            <dd className="mt-1 text-as-text">
              {(
                gates?.validated_requires || [
                  "WALK_FORWARD",
                  "DSR",
                  "PBO",
                  "SENSITIVITY",
                  "COST",
                  "BOOTSTRAP",
                  "REGIME",
                  "SPA",
                ]
              ).join(" · ")}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide">尚未接入</dt>
            <dd className="mt-1">
              {(gates?.missing || []).join(" · ") || "—"}
            </dd>
          </div>
        </dl>
      </Card>

      <Card>
        <CardHeader
          title="Walk-forward"
          hint={
            <p className="text-xs text-as-muted">
              每折一次完整 LEAN 运行，样本外拼接后评分。过拟合塌缩不能进入
              VALIDATED。参数扫描在{" "}
              <Link
                href="/experiments"
                className="text-as-primary hover:underline"
              >
                实验
              </Link>
              。
            </p>
          }
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
              <Link
                href="/experiments"
                className="text-as-primary hover:underline"
              >
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
              对已完成回测的日收益做 stationary
              bootstrap。区间跨零则无统计显著性。
            </p>
          }
        />
        <BootstrapForm />
      </Card>

      {latestBoot && (latestBoot.status === "COMPLETED" || latestBoot.error) ? (
        <BootstrapReport run={latestBoot} />
      ) : null}

      <Card>
        <CardHeader
          title="制度稳定性"
          hint={
            <p className="text-xs text-as-muted">
              按市场状态分段看 Sharpe
              与胜率。只在单一制度有效的策略会被标注；互补制度为负则不能进入
              VALIDATED。
            </p>
          }
        />
        <RegimeForm />
      </Card>

      {latestRegime &&
      (latestRegime.status === "COMPLETED" || latestRegime.error) ? (
        <RegimeReport run={latestRegime} />
      ) : null}

      <Card>
        <CardHeader
          title="Reality Check / SPA"
          hint={
            <p className="text-xs text-as-muted">
              对同一家族试验台账做 White Reality Check 与 Hansen SPA。闸门是
              SPA_c，不是最好那条试验的原始 Sharpe。
            </p>
          }
        />
        <SpaForm />
      </Card>

      {latestSpa && (latestSpa.status === "COMPLETED" || latestSpa.error) ? (
        <SpaReport run={latestSpa} />
      ) : null}

      {isLoading ? (
        <Card className="h-40 animate-pulse bg-as-secondary" />
      ) : error ? (
        <Card>
          <EmptyState
            title="API 未连接"
            description="请先启动 FastAPI 服务（端口 8000）。"
          />
        </Card>
      ) : !items.length ? (
        <Card className="min-h-[240px]">
          <EmptyState
            icon={BadgeCheck}
            title="还没有验证记录"
            description="跑完一次回测后会写下 Deflated Sharpe、Bootstrap 与制度切片。Walk-forward、DSR、PBO、敏感性高原、成本、Sharpe 区间、制度稳定性与 Hansen SPA_c 都通过后，系统才会把策略标成已验证。"
          />
        </Card>
      ) : (
        <Card className="p-0">
          <div className="border-b border-as-border px-5 py-3 text-sm font-medium">
            验证运行
          </div>
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
                const pbo =
                  typeof row.result.pbo === "number" ? row.result.pbo : null;
                const dsr =
                  typeof row.result.dsr === "number" ? row.result.dsr : null;
                const n =
                  typeof row.result.n_trials === "number"
                    ? row.result.n_trials
                    : null;
                const oos =
                  typeof row.result.combined_oos_sharpe === "number"
                    ? row.result.combined_oos_sharpe
                    : null;
                const shape =
                  typeof row.result.shape === "string"
                    ? row.result.shape
                    : null;
                const breakeven =
                  typeof row.result.breakeven_bps === "number"
                    ? row.result.breakeven_bps
                    : null;
                const sharpeCi = asInterval(row.result.sharpe);
                const concentrated =
                  typeof row.result.concentrated_in === "string"
                    ? row.result.concentrated_in
                    : null;
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
                            : row.kind === "REGIME"
                              ? concentrated
                                ? `集中 ${concentrated}`
                                : row.passed
                                  ? "跨制度"
                                  : "未通过"
                              : row.kind === "SPA"
                                ? typeof row.result.p_spa_consistent ===
                                  "number"
                                  ? `SPA_c ${row.result.p_spa_consistent.toFixed(3)}`
                                  : "—"
                                : oos == null
                                  ? "—"
                                  : `OOS Sharpe ${oos.toFixed(2)}`;
                return (
                  <tr
                    key={row.id}
                    className="border-b border-as-border last:border-0"
                  >
                    <td className="px-5 py-3 font-medium">{row.kind}</td>
                    <td className="px-5 py-3 text-xs text-as-muted">
                      {row.status}
                    </td>
                    <td className="px-5 py-3">
                      <Badge tone={badge.tone}>{badge.label}</Badge>
                      {row.error?.message ? (
                        <p className="mt-1 text-xs text-as-muted">
                          {row.error.message}
                        </p>
                      ) : null}
                    </td>
                    <td className="px-5 py-3 tabular-nums text-as-muted">
                      {summary}
                    </td>
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
