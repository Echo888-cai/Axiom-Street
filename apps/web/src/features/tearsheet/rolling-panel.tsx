"use client";

import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { RollingChart } from "@/components/charts/rolling-chart";
import type { RollingPoint } from "@/lib/tearsheet";

export function RollingPanel({
  sharpe,
  sharpeError,
  beta,
  betaError,
}: {
  sharpe: RollingPoint[];
  sharpeError?: string;
  beta: RollingPoint[];
  betaError?: string;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader
          title="滚动夏普"
          hint={<span className="text-[11px] text-as-muted">Axiom 从权益收益计算，不用 LEAN RollingWindow 顶替</span>}
        />
        {sharpeError || !sharpe.length ? (
          <EmptyState title="还没有滚动夏普" description={sharpeError || "需要足够长的权益序列。"} />
        ) : (
          <RollingChart
            data={sharpe.map((p) => ({ time: p.time, value: p.sharpe }))}
            caption="63 个交易日窗口 · 年化 √252 · 由权益收益序列计算"
          />
        )}
      </Card>
      <Card>
        <CardHeader
          title="滚动波动率"
          hint={<span className="text-[11px] text-as-muted">样本标准差 · 年化 √252</span>}
        />
        {sharpeError || !sharpe.length ? (
          <EmptyState title="还没有滚动波动率" description={sharpeError || "需要足够长的权益序列。"} />
        ) : (
          <RollingChart
            data={sharpe.map((p) => ({ time: p.time, value: p.volatility }))}
            color="#667085"
            caption="与滚动夏普同一窗口"
          />
        )}
      </Card>
      <Card>
        <CardHeader
          title="滚动 β"
          hint={<span className="text-[11px] text-as-muted">对基准收益的 OLS β，不是超额收益</span>}
        />
        {betaError || !beta.length ? (
          <EmptyState title="还没有滚动 β" description={betaError || "需要配对的基准净值。"} />
        ) : (
          <RollingChart
            data={beta
              .filter((p) => p.beta != null)
              .map((p) => ({ time: p.time, value: p.beta as number }))}
            color="#12B76A"
            caption="Cov(r, r_b) / Var(r_b) · 63 日"
          />
        )}
      </Card>
      <Card>
        <CardHeader
          title="滚动相关"
          hint={<span className="text-[11px] text-as-muted">与基准日收益的 Pearson 相关</span>}
        />
        {betaError || !beta.some((p) => p.correlation != null) ? (
          <EmptyState title="还没有滚动相关" description={betaError || "需要配对的基准净值。"} />
        ) : (
          <RollingChart
            data={beta
              .filter((p) => p.correlation != null)
              .map((p) => ({ time: p.time, value: p.correlation as number }))}
            color="#F04438"
            caption="同一 63 日窗口"
          />
        )}
      </Card>
    </div>
  );
}
