"use client";

import type { BacktestMetrics } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { HistogramChart } from "@/components/charts/histogram-chart";
import { QqChart } from "@/components/charts/qq-chart";
import { MetricTile } from "@/components/ui/metric-tile";
import { formatNumber, formatPct } from "@/lib/utils";
import type { HistogramBin, QqPoint } from "@/lib/tearsheet";

export function DistributionPanel({
  metrics,
  bins,
  qq,
  error,
}: {
  metrics: BacktestMetrics | undefined;
  bins: HistogramBin[];
  qq: QqPoint[];
  error?: string;
}) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <MetricTile label="VaR 95%" value={formatPct(num(metrics?.var_95))} hint="日损失分位，来自收益序列" />
        <MetricTile label="CVaR 95%" value={formatPct(num(metrics?.cvar_95))} hint="尾部均值损失" />
        <MetricTile label="尾部比" value={formatNumber(num(metrics?.tail_ratio))} hint="上 5% / |下 5%|" />
        <MetricTile label="偏度" value={formatNumber(num(metrics?.skewness))} />
        <MetricTile label="超额峰度" value={formatNumber(num(metrics?.kurtosis))} />
        <MetricTile label="Omega" value={formatNumber(num(metrics?.omega_ratio))} hint="正收益和 / |负收益和|" />
      </div>
      {error ? (
        <Card>
          <p className="text-sm text-as-muted">{error}</p>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader
              title="日收益分布"
              hint={<span className="text-[11px] text-as-muted">由权益差分，不是模拟直方图</span>}
            />
            <HistogramChart bins={bins} />
          </Card>
          <Card>
            <CardHeader
              title="正态 QQ"
              hint={<span className="text-[11px] text-as-muted">虚线为 y = x；偏离表示尾部或偏度</span>}
            />
            <div className="flex justify-center">
              <QqChart points={qq} />
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
