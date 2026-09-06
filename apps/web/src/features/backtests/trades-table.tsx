"use client";

import { Card } from "@/components/ui/card";
import type { Trade } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { labelDirection } from "@/lib/labels";

export function TradesTable({ rows }: { rows: Trade[] }) {
  const headers = [
    "日期",
    "标的",
    "方向",
    "数量",
    "入场价",
    "出场价",
    "盈亏",
    "持有期",
    "佣金",
  ];
  return (
    <Card className="overflow-hidden p-0">
      <div className="border-b border-as-border px-5 py-4">
        <div className="text-sm font-medium">成交明细</div>
        <p className="mt-1 text-[11px] text-as-muted">
          出场价、盈亏、持有期来自 round-trip 配对；缺失时显示为空，不填假数。
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
            {rows.slice(0, 200).map((t) => {
              const dir = labelDirection(t.direction, t.quantity);
              const sell = dir === "卖出";
              return (
                <tr
                  key={t.id}
                  className="border-t border-as-border/70 hover:bg-as-secondary/50"
                >
                  <td className="px-4 py-2.5 tabular">
                    {t.trade_date.slice(0, 10)}
                  </td>
                  <td className="px-4 py-2.5">{t.ticker}</td>
                  <td
                    className={`px-4 py-2.5 ${sell ? "text-as-negative" : "text-as-positive"}`}
                  >
                    {dir}
                  </td>
                  <td className="px-4 py-2.5 tabular">
                    {formatNumber(t.quantity, 0)}
                  </td>
                  <td className="px-4 py-2.5 tabular">
                    {formatNumber(t.entry_price)}
                  </td>
                  <td className="px-4 py-2.5 tabular">
                    {formatNumber(t.exit_price)}
                  </td>
                  <td className="px-4 py-2.5 tabular">
                    {formatNumber(t.pnl)}
                  </td>
                  <td className="px-4 py-2.5 tabular">
                    {formatNumber(t.holding_period, 0)}
                  </td>
                  <td className="px-4 py-2.5 tabular">
                    {formatNumber(t.commission)}
                  </td>
                </tr>
              );
            })}
            {!rows.length ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-as-muted">
                  暂无成交记录。
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
