"use client";

import { Card } from "@/components/ui/card";
import type { Trade } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { labelDirection } from "@/lib/labels";
import { useT } from "@/lib/i18n";

export function TradesTable({ rows }: { rows: Trade[] }) {
  const t = useT();
  const headers = [
    t("backtest.tradeColumns.date"),
    t("backtest.tradeColumns.ticker"),
    t("backtest.tradeColumns.direction"),
    t("backtest.tradeColumns.quantity"),
    t("backtest.tradeColumns.entry"),
    t("backtest.tradeColumns.exit"),
    t("backtest.tradeColumns.pnl"),
    t("backtest.tradeColumns.holdingPeriod"),
    t("backtest.tradeColumns.commission"),
  ];
  return (
    <Card className="overflow-hidden p-0">
      <div className="border-b border-as-border px-5 py-4">
        <div className="text-sm font-medium">{t("backtest.tradesPanel.title")}</div>
        <p className="mt-1 text-[11px] text-as-muted">
          {t("backtest.tradesPanel.note")}
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] text-left text-xs">
          <thead className="sticky top-0 bg-as-secondary/90 text-as-muted backdrop-blur-sm">
            <tr>
              {headers.map((h) => (
                <th key={h} className="px-4 py-3 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 200).map((row) => {
              const dir = labelDirection(row.direction, row.quantity);
              const sell =
                row.quantity != null && row.quantity !== 0
                  ? row.quantity < 0
                  : ["SELL", "-1"].includes(String(row.direction).toUpperCase());
              return (
                <tr
                  key={row.id}
                  className="border-t border-as-border/70 hover:bg-as-secondary/50"
                >
                  <td className="px-4 py-2.5 tabular">
                    {row.trade_date.slice(0, 10)}
                  </td>
                  <td className="px-4 py-2.5">{row.ticker}</td>
                  <td
                    className={`px-4 py-2.5 ${sell ? "text-as-negative" : "text-as-positive"}`}
                  >
                    {dir}
                  </td>
                  <td className="px-4 py-2.5 tabular">
                    {formatNumber(row.quantity, 0)}
                  </td>
                  <td className="px-4 py-2.5 tabular">
                    {formatNumber(row.entry_price)}
                  </td>
                  <td className="px-4 py-2.5 tabular">
                    {formatNumber(row.exit_price)}
                  </td>
                  <td className="px-4 py-2.5 tabular">
                    {formatNumber(row.pnl)}
                  </td>
                  <td className="px-4 py-2.5 tabular">
                    {formatNumber(row.holding_period, 0)}
                  </td>
                  <td className="px-4 py-2.5 tabular">
                    {formatNumber(row.commission)}
                  </td>
                </tr>
              );
            })}
            {!rows.length ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-as-muted">
                  {t("backtest.tradesPanel.empty")}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
