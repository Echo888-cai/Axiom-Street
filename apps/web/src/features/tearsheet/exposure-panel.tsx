"use client";

import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ExposureChart, type ExposurePoint } from "@/components/charts/exposure-chart";
import { RollingChart } from "@/components/charts/rolling-chart";
import { formatNumber } from "@/lib/utils";
import { chartColors } from "@/lib/chart-tokens";
import { useT } from "@/lib/i18n";

export function ExposurePanel({
  points,
  turnover,
  gross,
  net,
}: {
  points: ExposurePoint[];
  turnover: { time: string; value: number }[];
  gross: number | null | undefined;
  net: number | null | undefined;
}) {
  const t = useT();
  if (!points.length) {
    return (
      <Card>
        <EmptyState
          title={t("tearsheet.expPanel.noDataTitle")}
          description={t("tearsheet.expPanel.noDataDesc")}
        />
      </Card>
    );
  }
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title={t("tearsheet.expPanel.title")}
          hint={
            <span className="text-[11px] text-as-muted">
              {t("tearsheet.expPanel.hint")
                .replace("{gross}", formatNumber(gross))
                .replace("{net}", formatNumber(net))}
            </span>
          }
        />
        <ExposureChart data={points} />
      </Card>
      <Card>
        <CardHeader title={t("tearsheet.expPanel.turnoverTitle")} hint={<span className="text-[11px] text-as-muted">{t("tearsheet.expPanel.turnoverHint")}</span>} />
        {turnover.length ? (
          <RollingChart data={turnover} color={chartColors.muted} caption={t("tearsheet.expPanel.turnoverCaption")} />
        ) : (
          <EmptyState title={t("tearsheet.expPanel.noTurnoverTitle")} description={t("tearsheet.expPanel.noTurnoverDesc")} />
        )}
      </Card>
    </div>
  );
}
