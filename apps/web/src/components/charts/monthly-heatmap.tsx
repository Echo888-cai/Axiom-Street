"use client";

import type { MonthlyReturn } from "@/lib/api";
import { cn } from "@/lib/utils";

const MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];

function cellColor(value: number | null): string {
  if (value === null) return "bg-aq-secondary text-aq-muted";
  const intensity = Math.min(Math.abs(value) / 0.08, 1);
  if (value >= 0) {
    return `text-aq-positive`;
  }
  return `text-aq-negative`;
  // keep intensity via inline style
  void intensity;
}

export function MonthlyHeatmap({ data }: { data: MonthlyReturn[] }) {
  const years = Array.from(new Set(data.map((d) => d.year))).sort((a, b) => b - a);
  const map = new Map(data.map((d) => [`${d.year}-${d.month}`, d.return_pct]));

  if (!data.length) {
    return <p className="text-sm text-aq-muted">暂无月度收益。</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-xs">
        <thead>
          <tr className="text-aq-muted">
            <th className="px-2 py-2 text-left font-medium">年份</th>
            {MONTHS.map((m) => (
              <th key={m} className="px-2 py-2 text-right font-medium">
                {m}
              </th>
            ))}
            <th className="px-2 py-2 text-right font-medium">本年</th>
          </tr>
        </thead>
        <tbody>
          {years.map((year) => {
            const vals = MONTHS.map((_, idx) => map.get(`${year}-${idx + 1}`) ?? null);
            const present = vals.filter((v): v is number => v !== null);
            const ytd =
              present.length > 0
                ? present.reduce((acc, v) => (1 + acc) * (1 + v) - 1, 0)
                : null;
            return (
              <tr key={year} className="border-t border-aq-border/70">
                <td className="px-2 py-2 font-medium text-aq-text">{year}</td>
                {vals.map((v, i) => (
                  <td
                    key={i}
                    className={cn("px-2 py-2 text-right tabular", cellColor(v))}
                    style={
                      v === null
                        ? undefined
                        : {
                            backgroundColor:
                              v >= 0
                                ? `rgba(18,183,106,${0.08 + Math.min(Math.abs(v) / 0.08, 1) * 0.2})`
                                : `rgba(240,68,56,${0.08 + Math.min(Math.abs(v) / 0.08, 1) * 0.2})`,
                          }
                    }
                  >
                    {v === null ? "—" : `${(v * 100).toFixed(1)}`}
                  </td>
                ))}
                <td className={cn("px-2 py-2 text-right font-medium tabular", cellColor(ytd))}>
                  {ytd === null ? "—" : `${(ytd * 100).toFixed(1)}`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
