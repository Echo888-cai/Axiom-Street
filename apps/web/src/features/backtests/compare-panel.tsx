"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectItem } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { EquityCurve } from "@/components/charts/equity-curve";
import { api, type Backtest, type CompareSeries } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { useT } from "@/lib/i18n";

interface ComparePanelProps {
  currentBacktestId: string;
}

export function ComparePanel({ currentBacktestId }: ComparePanelProps) {
  const t = useT();
  const [selectedIds, setSelectedIds] = useState<string[]>([currentBacktestId]);
  const [normalized, setNormalized] = useState(false);
  const [period, setPeriod] = useState<"1M" | "3M" | "YTD" | "1Y" | "ALL">("ALL");

  const { data: allBacktests } = useQuery<Backtest[]>({
    queryKey: ["backtests", "all", "COMPLETED"],
    queryFn: () => api.listBacktests({ status: "COMPLETED" }),
  });

  const { data: compareData } = useQuery({
    queryKey: ["compare", "equity", [...selectedIds].sort().join(","), normalized, period],
    queryFn: () => api.compareEquity(selectedIds, normalized),
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
        title={t("backtest.compare.title")}
        hint={<span className="text-xs text-muted-foreground">{t("backtest.compare.hint")}</span>}
      />
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[280px]">
            <Label htmlFor="backtest-select">{t("backtest.compare.selectLabel")}</Label>
            <div className="flex flex-wrap gap-2 pt-1" id="backtest-select">
              {availableBacktests.length === 0 ? (
                <span className="text-xs text-muted-foreground">{t("backtest.compare.noCompleted")}</span>
              ) : (
                availableBacktests.map((bt) => {
                  const selected = selectedIds.includes(bt.id);
                  return (
                    <button
                      key={bt.id}
                      type="button"
                      onClick={() => handleToggle(bt.id)}
                      aria-pressed={selected}
                      className={
                        "flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition-colors " +
                        (selected
                          ? "border-as-primary bg-as-primary/10 text-as-primary"
                          : "border-as-border text-as-muted hover:border-as-primary/40")
                      }
                    >
                      <span className="font-medium">{bt.strategy_name || "Unknown"}</span>
                      <span className="tabular text-as-muted">
                        v{bt.version_number || "?"} · {bt.start_date.slice(0, 10)}
                      </span>
                      {selected ? <span aria-hidden>✓</span> : null}
                    </button>
                  );
                })
              )}
            </div>
            {selectedIds.length < 2 && (
              <p className="mt-1 text-xs text-amber-600">{t("backtest.compare.minTwo")}</p>
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
              <span className="text-muted-foreground">{t("backtest.compare.normalized")}</span>
            </label>
            <div className="space-y-1">
              <Label htmlFor="period">{t("backtest.compare.period")}</Label>
              <Select
                value={period}
                onChange={(e) => setPeriod(e.target.value as typeof period)}
                className="w-[140px]"
              >
                <SelectItem value="1M">{t("backtest.compare.periods.m1")}</SelectItem>
                <SelectItem value="3M">{t("backtest.compare.periods.m3")}</SelectItem>
                <SelectItem value="YTD">{t("backtest.compare.periods.ytd")}</SelectItem>
                <SelectItem value="1Y">{t("backtest.compare.periods.y1")}</SelectItem>
                <SelectItem value="ALL">{t("backtest.period.all")}</SelectItem>
              </Select>
            </div>
          </div>
        </div>

        {selectedIds.length >= 2 && compareData?.series?.length && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex flex-wrap gap-2">
                {compareData.series.map((s: CompareSeries, i: number) => (
                  <Badge
                    key={s.id}
                    tone={(["blue", "green", "amber", "red", "neutral"] as const)[i % 5]}
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
                <span className="text-muted-foreground">{t("backtest.compare.normalized")}</span>
              </label>
            </div>

            <EquityCurve
              series={compareData.series.map((s: CompareSeries) => ({
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
                    <th className="px-4 py-2 font-medium">{t("backtest.compare.table.strategy")}</th>
                    <th className="px-4 py-2 font-medium tabular">{t("backtest.compare.table.finalEquity")}</th>
                    <th className="px-4 py-2 font-medium tabular">{t("backtest.compare.table.totalReturn")}</th>
                    <th className="px-4 py-2 font-medium tabular">{t("backtest.compare.table.cagr")}</th>
                    <th className="px-4 py-2 font-medium tabular">{t("backtest.compare.table.sharpe")}</th>
                    <th className="px-4 py-2 font-medium tabular">{t("backtest.compare.table.maxDD")}</th>
                    <th className="px-4 py-2 font-medium tabular">{t("backtest.compare.table.volatility")}</th>
                    <th className="px-4 py-2 font-medium tabular">{t("backtest.compare.table.trades")}</th>
                  </tr>
                </thead>
                <tbody>
                  {compareData.series.map((s: CompareSeries, i: number) => {
                    const lastPoint = s.data[s.data.length - 1];
                    const firstPoint = s.data[0];
                    const totalRet = firstPoint && lastPoint
                      ? ((lastPoint.value / firstPoint.value - 1) * 100).toFixed(2)
                      : "—";
                    return (
                      <tr key={s.id} className="border-b border-as-border last:border-0 hover:bg-as-secondary/50">
                        <td className="px-4 py-3 font-medium">
                          <Badge tone={(["blue", "green", "amber", "red", "neutral"] as const)[i % 5]}>
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
          </div>
        )}
      </CardContent>
    </Card>
  );
}
