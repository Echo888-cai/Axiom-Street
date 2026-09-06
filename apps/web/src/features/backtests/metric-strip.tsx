"use client";

import { MetricTile, metricTone } from "@/components/ui/metric-tile";
import type { BacktestMetrics } from "@/lib/api";
import { formatNumber, formatPct, formatUsd } from "@/lib/utils";
import { useT } from "@/lib/i18n";

export function MetricStrip({ m }: { m: BacktestMetrics | undefined }) {
  const t = useT();
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6 as-stagger">
      <MetricTile label={t("backtest.metrics.totalReturn")} value={formatPct(m?.total_return)} tone={metricTone(m?.total_return)} />
      <MetricTile label={t("backtest.metricStrip.cagr")} value={formatPct(m?.cagr)} tone={metricTone(m?.cagr)} />
      <MetricTile label={t("backtest.metrics.maxDrawdown")} value={formatPct(m?.max_drawdown)} tone="neg" />
      <MetricTile label={t("backtest.metrics.volatility")} value={formatPct(m?.volatility)} />
      <MetricTile label={t("backtest.metricStrip.excessReturn")} value={formatPct(m?.excess_return)} tone={metricTone(m?.excess_return)} />
      <MetricTile label={t("backtest.metricStrip.alpha")} value={formatPct(m?.alpha_capm)} tone={metricTone(m?.alpha_capm)} />
      <MetricTile label={t("backtest.metricStrip.beta")} value={formatNumber(m?.beta)} />
      <MetricTile label={t("backtest.metricStrip.informationRatio")} value={formatNumber(m?.information_ratio)} />
      <MetricTile label={t("backtest.metricStrip.sortino")} value={formatNumber(m?.sortino)} />
      <MetricTile label={t("backtest.metricStrip.calmar")} value={formatNumber(m?.calmar)} />
      <MetricTile label={t("backtest.metricStrip.tradeCount")} value={formatNumber(m?.trade_count, 0)} />
      <MetricTile label={t("backtest.compare.table.finalEquity")} value={formatUsd(m?.final_equity)} />
    </div>
  );
}
