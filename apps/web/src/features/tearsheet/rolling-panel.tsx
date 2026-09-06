"use client";

import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { RollingChart } from "@/components/charts/rolling-chart";
import { chartColors } from "@/lib/chart-tokens";
import type { RollingPoint } from "@/lib/tearsheet";
import { useT } from "@/lib/i18n";

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
  const t = useT();
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader
          title={t("tearsheet.rollPanel.sharpeTitle")}
          hint={<span className="text-[11px] text-as-muted">{t("tearsheet.rollPanel.sharpeHint")}</span>}
        />
        {sharpeError || !sharpe.length ? (
          <EmptyState title={t("tearsheet.rollPanel.noSharpe")} description={sharpeError || t("tearsheet.rollPanel.needLongEquity")} />
        ) : (
          <RollingChart
            data={sharpe.map((p) => ({ time: p.time, value: p.sharpe }))}
            caption={t("tearsheet.rollPanel.sharpeCaption")}
          />
        )}
      </Card>
      <Card>
        <CardHeader
          title={t("tearsheet.rollPanel.volTitle")}
          hint={<span className="text-[11px] text-as-muted">{t("tearsheet.rollPanel.volHint")}</span>}
        />
        {sharpeError || !sharpe.length ? (
          <EmptyState title={t("tearsheet.rollPanel.noVol")} description={sharpeError || t("tearsheet.rollPanel.needLongEquity")} />
        ) : (
          <RollingChart
            data={sharpe.map((p) => ({ time: p.time, value: p.volatility }))}
            color={chartColors.muted}
            caption={t("tearsheet.rollPanel.volCaption")}
          />
        )}
      </Card>
      <Card>
        <CardHeader
          title={t("tearsheet.rollPanel.betaTitle")}
          hint={<span className="text-[11px] text-as-muted">{t("tearsheet.rollPanel.betaHint")}</span>}
        />
        {betaError || !beta.length ? (
          <EmptyState title={t("tearsheet.rollPanel.noBeta")} description={betaError || t("tearsheet.rollPanel.needBenchmark")} />
        ) : (
          <RollingChart
            data={beta
              .filter((p) => p.beta != null)
              .map((p) => ({ time: p.time, value: p.beta as number }))}
            color={chartColors.positive}
            caption={t("tearsheet.rollPanel.betaCaption")}
          />
        )}
      </Card>
      <Card>
        <CardHeader
          title={t("tearsheet.rollPanel.corrTitle")}
          hint={<span className="text-[11px] text-as-muted">{t("tearsheet.rollPanel.corrHint")}</span>}
        />
        {betaError || !beta.some((p) => p.correlation != null) ? (
          <EmptyState title={t("tearsheet.rollPanel.noCorr")} description={betaError || t("tearsheet.rollPanel.needBenchmark")} />
        ) : (
          <RollingChart
            data={beta
              .filter((p) => p.correlation != null)
              .map((p) => ({ time: p.time, value: p.correlation as number }))}
            color={chartColors.negative}
            caption={t("tearsheet.rollPanel.corrCaption")}
          />
        )}
      </Card>
    </div>
  );
}
