"use client";

import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ExposureChart, type ExposurePoint } from "@/components/charts/exposure-chart";
import { RollingChart } from "@/components/charts/rolling-chart";
import { formatNumber } from "@/lib/utils";

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
  if (!points.length) {
    return (
      <Card>
        <EmptyState
          title="没有暴露序列"
          description="这次回测没有解析到 LEAN 的 Exposure 图。这里不填 0。"
        />
      </Card>
    );
  }
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="持仓暴露"
          hint={
            <span className="text-[11px] text-as-muted">
              多头 / 空头来自 LEAN Exposure 图 · 均值 毛 {formatNumber(gross)} / 净 {formatNumber(net)}
            </span>
          }
        />
        <ExposureChart data={points} />
      </Card>
      <Card>
        <CardHeader title="换手" hint={<span className="text-[11px] text-as-muted">Portfolio Turnover 图</span>} />
        {turnover.length ? (
          <RollingChart data={turnover} color="#667085" caption="LEAN Portfolio Turnover 序列" />
        ) : (
          <EmptyState title="没有换手序列" description="LEAN 没有写出 Portfolio Turnover 图。" />
        )}
      </Card>
    </div>
  );
}
