"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { EquityCurve } from "@/components/charts/equity-curve";
import { api, type Backtest } from "@/lib/api";
import { formatPct, formatNumber } from "@/lib/utils";
import { useT, useI18n } from "@/lib/i18n";

interface ComparePanelProps {
  currentBacktestId: string;
}

export function ComparePanel({ currentBacktestId }: ComparePanelProps) {
  const t = useT();
  const i18n = useI18n();
  const [selectedIds, setSelectedIds] = useState<string[]>([currentBacktestId]);
  const [normalized, setNormalized] = useState(false);
  const [period, setPeriod] = useState<"1M" | "3M" | "YTD" | "1Y" | "ALL">("ALL");

  const { data: allBacktests } = useQuery<Backtest[]>({
    queryKey: ["backtests", "all", "COMPLETED"],
    queryFn: () => api.listBacktests({ status: "COMPLETED", limit: 200 }).then((r) => r.items),
  });

  const { data: compareData } = useQuery({
    queryKey: ["compare", "equity", selectedIds.sort().join(","), normalized, period],
    queryFn: () => api.get("/api/v1/backtests/compare/equity", {
      params: { ids: selectedIds, normalized },
    }),
    enabled: selectedIds.length >= 2,
  });

  const availableBacktests = allBacktests?.filter((b) => b.status === "COMPLETED") || [];

  const handleToggle = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id].slice(0, 6)
    );
  };

  return (
    <Card className="mt-4">
      <CardHeader
        title={i18n?.backtest?.compare?.title || "多回测对比"}
        hint={<span className="text-xs text-muted-foreground">选择 2-6 个已完成的回测进行跨策略对比</span>}
      />
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[280px]">
            <Label htmlFor="backtest-select">{t("backtest.compare.selectLabel") || "选择回测"}</Label>
            <Select
              value={selectedIds.join(",")}
              onValueChange={() => {}}
              className="w-full"
              multiple
            >
              <SelectTrigger className="min-h-[42px]">
                <SelectValue placeholder={t("common.select") || "选择..."} />
              </SelectTrigger>
              <SelectContent>
                {availableBacktests.map((bt) => (
                  <SelectItem key={bt.id} value={bt.id}>
                    <div className="flex items-center gap-2 py-1.5">
                      <Badge
                        tone={bt.id === currentBacktestId ? "blue" : "neutral"}
                        className="text-[10px]"
                      >
                        {bt.strategy_name || "Unknown"}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        v{bt.version_number || "?"} · {bt.start_date.slice(0, 10)} → {bt.end_date.slice(0, 10)}
                      </span>
                      {bt.id === currentBacktestId && (
                        <Badge tone="green" className="text-[9px]">当前</Badge>
                      )}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedIds.length < 2 && (
              <p className="mt-1 text-xs text-amber-600">至少选择 2 个回测</p>
            )}
          </div>

          <div className="flex items-end gap-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={normalized}
                onChange={(e) => setNormalized(e.target.checked)}
                className="accent-as-primary"
              />
              <span className="text-muted-foreground">{t("backtest.compare.normalized") || "归一化到 100"}</span>
            </label>
            <div className="space-y-1">
              <Label htmlFor="period">{t("backtest.compare.period") || "周期"}</Label>
              <Select value={period} onValueChange={setPeriod}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1M">1 月</SelectItem>
                  <SelectItem value="3M">3 月</SelectItem>
                  <SelectItem value="YTD">今年以来</SelectItem>
                  <SelectItem value="1Y">1 年</SelectItem>
                  <SelectItem value="ALL">全部</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        {selectedIds.length >= 2 && compareData?.series?.length && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex flex-wrap gap-2">
                {compareData.series.map((s: any, i: number) => (
                  <Badge
                    key={s.id}
                    tone={["blue", "green", "amber", "purple", "pink", "cyan"][i % 6] as any}
                    className="cursor-pointer hover:opacity-80"
                  >
                    {s.label}
                  </Badge>
                ))}
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={normalized}
                  onChange={(e) => setNormalized(e.target.checked)}
                  className="accent-as-primary"
                />
                <span className="text-muted-foreground">{t("backtest.compare.normalized") || "归一化到 100"}</span>
              </label>
            </div>

            <EquityCurve
              series={compareData.series.map((s: any) => ({
                id: s.id,
                label: s.label,
                data: s.data,
                color: [
                  "var(--as-primary)",
                  "var(--as-positive)",
                  "var(--as-negative)",
                  "var(--as-warning)",
                  "var(--as-primary-soft)",
                  "var(--as-muted)",
                ][compareData.series.indexOf(s) % 6],
                dashed: false,
              }))}
              height={380}
              logScale={false}
            />

            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] text-left text-sm">
                <thead className="sticky top-0 bg-as-secondary/90 text-as-muted backdrop-blur-sm">
                  <tr className="border-b border-as-border">
                    <th className="px-4 py-2 font-medium">{t("backtest.compare.table.strategy") || "策略"}</th>
                    <th className="px-4 py-2 font-medium tabular">{t("backtest.compare.table.finalEquity") || "期末权益"}</th>
                    <th className="px-4 py-2 font-medium tabular">{t("backtest.compare.table.totalReturn") || "总收益"}</th>
                    <th className="px-4 py-2 font-medium tabular">{t("backtest.compare.table.cagr") || "年化收益"}</th>
                    <th className="px-4 py-2 font-medium tabular">{t("backtest.compare.table.sharpe") || "夏普"}</th>
                    <th className="px-4 py-2 font-medium tabular">{t("backtest.compare.table.maxDD") || "最大回撤"}</th>
                    <th className="px-4 py-2 font-medium tabular">{t("backtest.compare.table.volatility") || "波动率"}</th>
                    <th className="px-4 py-2 font-medium tabular">{t("backtest.compare.table.trades") || "成交数"}</th>
                  </tr>
                </thead>
                <tbody>
                  {compareData.series.map((s: any, i: number) => {
                    const lastPoint = s.data[s.data.length - 1];
                    const firstPoint = s.data[0];
                    const totalRet = firstPoint && lastPoint
                      ? ((lastPoint.value / firstPoint.value - 1) * 100).toFixed(2)
                      : "—";
                    return (
                      <tr key={s.id} className="border-b border-as-border last:border-0 hover:bg-as-secondary/50">
                        <td className="px-4 py-3 font-medium">
                          <Badge tone={["blue", "green", "amber", "purple", "pink", "cyan"][i % 6] as any}>
                            {s.label}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 tabular text-as-text">{lastPoint ? formatNumber(lastPoint.value) : "—"}</td>
                        <td className="px-4 py-3 tabular text-as-text">{totalRet}%</td>
                        <td className="px-4 py-3 tabular text-as-text">{s.cagr?.toFixed(2) ?? "—"}</td>
                        <td className="px-4 py-3 tabular text-as-text">{s.sharpe?.toFixed(2) ?? "—"}</td>
                        <td className="px-4 py-3 tabular text-as-text">{s.maxDrawdown?.toFixed(2) ?? "—"}</td>
                        <td className="px-4 py-3 tabular text-as-text">{s.volatility?.toFixed(2) ?? "—"}</td>
                        <td className="px-4 py-3 tabular text-as-text">{s.tradeCount ?? "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}