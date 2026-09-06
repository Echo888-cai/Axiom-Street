"use client";

import type { MonthlyReturn } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

function cellColor(value: number | null): string {
  if (value === null) return "bg-as-secondary text-as-muted";
  const intensity = Math.min(Math.abs(value) / 0.08, 1);
  if (value >= 0) {
    return `text-as-positive`;
  }
  return `text-as-negative`;
  // keep intensity via inline style
  void intensity;
}

export function MonthlyHeatmap({ data }: { data: MonthlyReturn[] }) {
  const t = useT();
  const years = Array.from(new Set(data.map((d) => d.year))).sort(
    (a, b) => b - a,
  );
  const map = new Map(data.map((d) => [`${d.year}-${d.month}`, d.return_pct]));

  if (!data.length) {
    return <p className="text-sm text-as-muted">{t("tearsheet.heat.empty")}</p>;
  }

  const months = [
    t("tearsheet.heat.months.jan"),
    t("tearsheet.heat.months.feb"),
    t("tearsheet.heat.months.mar"),
    t("tearsheet.heat.months.apr"),
    t("tearsheet.heat.months.may"),
    t("tearsheet.heat.months.jun"),
    t("tearsheet.heat.months.jul"),
    t("tearsheet.heat.months.aug"),
    t("tearsheet.heat.months.sep"),
    t("tearsheet.heat.months.oct"),
    t("tearsheet.heat.months.nov"),
    t("tearsheet.heat.months.dec"),
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-xs">
        <thead>
          <tr className="text-as-muted">
            <th className="px-2 py-2 text-left font-medium">{t("tearsheet.heat.year")}</th>
            {months.map((m) => (
              <th key={m} className="px-2 py-2 text-right font-medium">
                {m}
              </th>
            ))}
            <th className="px-2 py-2 text-right font-medium">{t("tearsheet.heat.ytd")}</th>
          </tr>
        </thead>
        <tbody>
          {years.map((year) => {
            const vals = months.map(
              (_, idx) => map.get(`${year}-${idx + 1}`) ?? null,
            );
            const present = vals.filter((v): v is number => v !== null);
            const ytd =
              present.length > 0
                ? present.reduce((acc, v) => (1 + acc) * (1 + v) - 1, 0)
                : null;
            return (
              <tr key={year} className="border-t border-as-border/70">
                <td className="px-2 py-2 font-medium text-as-text">{year}</td>
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
                                ? `rgba(52,128,106,${0.08 + Math.min(Math.abs(v) / 0.08, 1) * 0.2})`
                                : `rgba(187,91,98,${0.08 + Math.min(Math.abs(v) / 0.08, 1) * 0.2})`,
                          }
                    }
                  >
                    {v === null ? "—" : `${(v * 100).toFixed(1)}`}
                  </td>
                ))}
                <td
                  className={cn(
                    "px-2 py-2 text-right font-medium tabular",
                    cellColor(ytd),
                  )}
                >
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
