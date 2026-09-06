"use client";

import type { BacktestMetrics } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { HistogramChart } from "@/components/charts/histogram-chart";
import { QqChart } from "@/components/charts/qq-chart";
import { MetricTile } from "@/components/ui/metric-tile";
import { formatNumber, formatPct } from "@/lib/utils";
import type { HistogramBin, QqPoint } from "@/lib/tearsheet";
import { useT } from "@/lib/i18n";

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
  const t = useT();
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <MetricTile label="VaR 95%" value={formatPct(num(metrics?.var_95))} hint={t("tearsheet.distPanel.varHint")} />
        <MetricTile label="CVaR 95%" value={formatPct(num(metrics?.cvar_95))} hint={t("tearsheet.distPanel.cvarHint")} />
        <MetricTile label={t("tearsheet.distPanel.tailRatioLabel")} value={formatNumber(num(metrics?.tail_ratio))} hint={t("tearsheet.distPanel.tailRatioHint")} />
        <MetricTile label={t("tearsheet.distPanel.skewLabel")} value={formatNumber(num(metrics?.skewness))} />
        <MetricTile label={t("tearsheet.distPanel.kurtosisLabel")} value={formatNumber(num(metrics?.kurtosis))} />
        <MetricTile label="Omega" value={formatNumber(num(metrics?.omega_ratio))} hint={t("tearsheet.distPanel.omegaHint")} />
      </div>
      {error ? (
        <Card>
          <p className="text-sm text-as-muted">{error}</p>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader
              title={t("tearsheet.distPanel.dailyTitle")}
              hint={<span className="text-[11px] text-as-muted">{t("tearsheet.distPanel.dailyHint")}</span>}
            />
            <HistogramChart bins={bins} />
          </Card>
          <Card>
            <CardHeader
              title={t("tearsheet.distPanel.qqTitle")}
              hint={<span className="text-[11px] text-as-muted">{t("tearsheet.distPanel.qqHint")}</span>}
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
