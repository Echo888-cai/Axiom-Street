"use client";

import { MetricTile, metricTone } from "@/components/ui/metric-tile";
import type { BacktestMetrics } from "@/lib/api";
import { formatNumber, formatPct, formatUsd } from "@/lib/utils";

export function MetricStrip({ m }: { m: BacktestMetrics | undefined }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6 as-stagger">
      <MetricTile label="总收益" value={formatPct(m?.total_return)} tone={metricTone(m?.total_return)} />
      <MetricTile label="年化 CAGR" value={formatPct(m?.cagr)} tone={metricTone(m?.cagr)} />
      <MetricTile label="最大回撤" value={formatPct(m?.max_drawdown)} tone="neg" />
      <MetricTile label="波动率" value={formatPct(m?.volatility)} />
      <MetricTile label="超额收益" value={formatPct(m?.excess_return)} tone={metricTone(m?.excess_return)} />
      <MetricTile label="CAPM α" value={formatPct(m?.alpha_capm)} tone={metricTone(m?.alpha_capm)} />
      <MetricTile label="β" value={formatNumber(m?.beta)} />
      <MetricTile label="信息比率" value={formatNumber(m?.information_ratio)} />
      <MetricTile label="索提诺" value={formatNumber(m?.sortino)} />
      <MetricTile label="卡尔玛" value={formatNumber(m?.calmar)} />
      <MetricTile label="成交笔数" value={formatNumber(m?.trade_count, 0)} />
      <MetricTile label="期末权益" value={formatUsd(m?.final_equity)} />
    </div>
  );
}
