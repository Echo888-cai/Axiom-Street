"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { EquityCurve } from "@/components/charts/equity-curve";
import { api, type MaeMfePoint } from "@/lib/api";
import { formatNumber, formatPct } from "@/lib/utils";
import { useT } from "@/lib/i18n";

interface MaeMfePanelProps {
  backtestId: string;
}

export function MaeMfePanel({ backtestId }: MaeMfePanelProps) {
  const t = useT();

  const { data: maeMfeData } = useQuery<MaeMfePoint[]>({
    queryKey: ["mae-mfe", backtestId],
    queryFn: () => api.getMaeMfe(backtestId),
  });

  if (!maeMfeData?.length) {
    return (
      <Card>
        <EmptyState
          title={t("backtest.maeMfe.noData") || "暂无 MAE/MFE 数据"}
          description={t("backtest.maeMfe.description") || "需要已完成且有成交记录的回测"}
        />
      </Card>
    );
  }

  const maeValues = maeMfeData.filter((d) => d.mae != null).map((d) => d.mae!);
  const mfeValues = maeMfeData.filter((d) => d.mfe != null).map((d) => d.mfe!);
  const holdingPeriods = maeMfeData.filter((d) => d.holding_period != null).map((d) => d.holding_period!);

  const avgMae = maeValues.length ? maeValues.reduce((a, b) => a + b, 0) / maeValues.length : 0;
  const avgMfe = mfeValues.length ? mfeValues.reduce((a, b) => a + b, 0) / mfeValues.length : 0;
  const avgHold = holdingPeriods.length ? holdingPeriods.reduce((a, b) => a + b, 0) / holdingPeriods.length : 0;

  const mfeMaeRatio = avgMae && avgMfe ? avgMfe / Math.abs(avgMae) : 0;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="MAE / MFE 分析"
          hint={<span className="text-[11px] text-muted-foreground">每笔交易的最大不利/有利波动 (MAE/MFE)</span>}
        />
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-4">
            <div className="rounded-lg border border-as-border bg-as-bg p-4">
              <div className="text-[11px] text-muted-foreground">平均 MAE</div>
              <div className="mt-1 text-2xl font-semibold tabular text-as-negative">
                {formatPct(avgMae)}
              </div>
            </div>
            <div className="rounded-lg border border-as-border bg-as-bg p-4">
              <div className="text-[11px] text-muted-foreground">平均 MFE</div>
              <div className="mt-1 text-2xl font-semibold tabular text-as-positive">
                {formatPct(avgMfe)}
              </div>
            </div>
            <div className="rounded-lg border border-as-border bg-as-bg p-4">
              <div className="text-[11px] text-muted-foreground">MFE/MAE 比</div>
              <div className="mt-1 text-2xl font-semibold tabular">
                {mfeMaeRatio.toFixed(2)}
              </div>
            </div>
            <div className="rounded-lg border border-as-border bg-as-bg p-4">
              <div className="text-[11px] text-muted-foreground">平均持仓期</div>
              <div className="mt-1 text-2xl font-semibold tabular">
                {avgHold.toFixed(1)} 天
              </div>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-as-border bg-as-bg p-4">
              <h4 className="text-sm font-medium mb-3">MAE 分布 (最大不利波动)</h4>
              <EquityCurve
                series={[
                  {
                    id: "mae",
                    label: "MAE",
                    data: maeValues
                      .sort((a, b) => a - b)
                      .map((v, i) => ({ time: String(i), value: v })),
                    color: "var(--as-negative)",
                  },
                ]}
                height={200}
              />
            </div>

            <div className="rounded-lg border border-as-border bg-as-bg p-4">
              <h4 className="text-sm font-medium mb-3">MFE 分布 (最大有利波动)</h4>
              <EquityCurve
                series={[
                  {
                    id: "mfe",
                    label: "MFE",
                    data: mfeValues
                      .sort((a, b) => a - b)
                      .map((v, i) => ({ time: String(i), value: v })),
                    color: "var(--as-positive)",
                  },
                ]}
                height={200}
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-as-border bg-as-bg p-4">
              <h4 className="text-sm font-medium mb-3">持仓期分布</h4>
              <EquityCurve
                series={[
                  {
                    id: "holding",
                    label: "持仓天数",
                    data: holdingPeriods
                      .sort((a, b) => a - b)
                      .map((v, i) => ({ time: String(i), value: v })),
                    color: "var(--as-primary)",
                  },
                ]}
                height={200}
              />
            </div>

            <div className="rounded-lg border border-as-border bg-as-bg p-4">
              <h4 className="text-sm font-medium mb-3">MFE vs MAE 散点</h4>
              <EquityCurve
                series={[
                  {
                    id: "scatter",
                    label: "MFE vs MAE",
                    data: maeMfeData
                      .filter((d) => d.mae != null && d.mfe != null)
                      .map((d) => ({ time: String(d.mae!), value: d.mfe! })),
                    color: "var(--as-primary)",
                  },
                ]}
                height={200}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader title="明细表" />
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-xs">
              <thead className="sticky top-0 bg-as-secondary/90 text-as-muted backdrop-blur-sm">
                <tr className="border-b border-as-border">
                  {[
                    "日期",
                    "标的",
                    "方向",
                    "入场价",
                    "出场价",
                    "盈亏",
                    "MAE",
                    "MFE",
                    "MFE/MAE",
                    "持仓期",
                  ].map((h) => (
                    <th key={h} className="px-3 py-2 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {maeMfeData.slice(0, 200).map((d) => (
                  <tr key={d.trade_id} className="border-b border-as-border/70 hover:bg-as-secondary/50">
                    <td className="px-3 py-2 tabular">{d.trade_date?.slice(0, 10)}</td>
                    <td className="px-3 py-2">{d.ticker}</td>
                    <td className="px-3 py-2">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                        d.direction === "BUY" || d.direction === "LONG"
                          ? "bg-as-positive/10 text-as-positive"
                          : "bg-as-negative/10 text-as-negative"
                      }`}>
                        {d.direction}
                      </span>
                    </td>
                    <td className="px-3 py-2 tabular">{d.entry_price ? formatNumber(d.entry_price) : "—"}</td>
                    <td className="px-3 py-2 tabular">{d.exit_price ? formatNumber(d.exit_price) : "—"}</td>
                    <td className="px-3 py-2 tabular text-as-text">{d.pnl ? formatNumber(d.pnl) : "—"}</td>
                    <td className="px-3 py-2 tabular text-as-negative">{d.mae ? formatPct(d.mae) : "—"}</td>
                    <td className="px-3 py-2 tabular text-as-positive">{d.mfe ? formatPct(d.mfe) : "—"}</td>
                    <td className="px-3 py-2 tabular text-as-text">
                      {d.mae && d.mfe && d.mae !== 0 ? (d.mfe / Math.abs(d.mae)).toFixed(2) : "—"}
                    </td>
                    <td className="px-3 py-2 tabular">{d.holding_period ? `${d.holding_period} 天` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}