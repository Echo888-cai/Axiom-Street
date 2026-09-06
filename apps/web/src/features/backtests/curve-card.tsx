"use client";

import { cn } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/card";
import { Tabs } from "@/components/ui/tabs";
import { EquityCurve, type EquityMarker, type EquitySeries } from "@/components/charts/equity-curve";
import { DrawdownChart } from "@/components/charts/drawdown-chart";
import type { Backtest } from "@/lib/api";
import { peerLabel } from "./use-backtest-analysis";
import { useT } from "@/lib/i18n";

function Toggle({
  pressed,
  onPressed,
  children,
  disabled,
}: {
  pressed: boolean;
  onPressed: () => void;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onPressed}
      className={cn(
        "h-8 rounded-lg px-2.5 text-[11px] font-medium outline-none transition-colors duration-as",
        "focus-visible:ring-2 focus-visible:ring-as-primary/30",
        pressed
          ? "bg-as-bg text-as-text shadow-sm"
          : "text-as-muted hover:text-as-text",
        disabled && "cursor-not-allowed opacity-40",
      )}
    >
      {children}
    </button>
  );
}

export function CurveCard({
  backtestId,
  series,
  markers,
  drawdownPoints,
  peers,
  canLog,
  logScale,
  onLogScale,
  normalized,
  onNormalized,
  showTrades,
  onShowTrades,
  compareId,
  onCompareId,
  period,
  onPeriod,
}: {
  backtestId: string;
  series: EquitySeries[];
  markers: EquityMarker[];
  drawdownPoints: React.ComponentProps<typeof DrawdownChart>["data"];
  peers: Backtest[];
  canLog: boolean;
  logScale: boolean;
  onLogScale: (v: boolean) => void;
  normalized: boolean;
  onNormalized: (v: boolean) => void;
  showTrades: boolean;
  onShowTrades: (v: boolean) => void;
  compareId: string;
  onCompareId: (id: string) => void;
  period: "1M" | "3M" | "YTD" | "1Y" | "ALL";
  onPeriod: (p: "1M" | "3M" | "YTD" | "1Y" | "ALL") => void;
}) {
  const t = useT();
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title={t("backtest.curve.title")}
          hint={
            <span className="text-[11px] text-as-muted">
              {normalized ? t("backtest.curve.hintNormalized") : t("backtest.curve.hintAbsolute")}
            </span>
          }
          action={
            <div className="flex flex-wrap items-center justify-end gap-2">
              <div className="inline-flex rounded-xl bg-as-secondary p-1">
                <Toggle pressed={logScale} disabled={!canLog} onPressed={() => onLogScale(!logScale)}>
                  {t("backtest.curve.log")}
                </Toggle>
                <Toggle pressed={normalized} onPressed={() => onNormalized(!normalized)}>
                  {t("backtest.curve.normalize100")}
                </Toggle>
                <Toggle pressed={showTrades} onPressed={() => onShowTrades(!showTrades)}>
                  {t("backtest.curve.tradeMarkers")}
                </Toggle>
              </div>
              <label className="flex items-center gap-1.5 text-[11px] text-as-muted">
                {t("backtest.curve.compare")}
                <select
                  className="h-8 max-w-[220px] rounded-lg border border-as-border bg-as-bg px-2 text-xs text-as-text outline-none focus:border-as-primary/40"
                  value={compareId}
                  onChange={(e) => onCompareId(e.target.value)}
                >
                  <option value="">{t("backtest.curve.noOverlay")}</option>
                  {peers
                    .filter((row) => row.id !== backtestId)
                    .map((row) => (
                      <option key={row.id} value={row.id}>
                        {peerLabel(row, false)}
                      </option>
                    ))}
                </select>
              </label>
              <Tabs
                value={period}
                onChange={(id) => onPeriod(id as typeof period)}
                items={[
                  { id: "1M", label: t("backtest.period.m1") },
                  { id: "3M", label: t("backtest.period.m3") },
                  { id: "YTD", label: t("backtest.period.ytd") },
                  { id: "1Y", label: t("backtest.period.y1") },
                  { id: "ALL", label: t("backtest.period.all") },
                ]}
              />
            </div>
          }
        />
        {!canLog && logScale ? (
          <p className="mb-3 text-xs text-as-negative">
            {t("backtest.curve.logUnavailable")}
          </p>
        ) : null}
        <EquityCurve
          series={series}
          logScale={logScale && canLog}
          markers={markers}
          height={340}
        />
      </Card>
      <Card>
        <CardHeader title={t("tearsheet.drawdown")} />
        <DrawdownChart data={drawdownPoints} />
      </Card>
    </div>
  );
}
