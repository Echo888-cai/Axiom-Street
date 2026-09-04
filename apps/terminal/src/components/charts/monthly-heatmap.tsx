import { cn } from "@/lib/cn";
import { fmtPct } from "@/lib/format";
import type { MonthlyGrid } from "@/mocks/types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Monthly returns heatmap — the classic tearsheet block, quietly rendered. */
export function MonthlyHeatmap({ grid }: { grid: MonthlyGrid }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <th className="py-1 pr-2 text-left text-[10px] font-medium text-text-3">Year</th>
            {MONTHS.map((m) => (
              <th key={m} className="px-0.5 py-1 text-center text-[10px] font-medium text-text-3">
                {m}
              </th>
            ))}
            <th className="py-1 pl-2 text-right text-[10px] font-medium text-text-3">Year</th>
          </tr>
        </thead>
        <tbody>
          {grid.years.map((year) => {
            const cells = grid.cells[year];
            const annual = cells.reduce<number | null>(
              (acc, v) => (v === null ? acc : (acc ?? 1) * (1 + v)),
              null,
            );
            return (
              <tr key={year}>
                <td className="mono py-px pr-2 text-[11px] text-text-3">{year}</td>
                {cells.map((v, i) => (
                  <td key={i} className="px-0.5 py-px">
                    <div
                      className={cn(
                        "mono flex h-6 items-center justify-center rounded-[3px] text-[10px]",
                        v === null && "text-transparent",
                      )}
                      style={{ background: cellBg(v), color: cellFg(v) }}
                      title={v === null ? undefined : `${MONTHS[i]} ${year}: ${fmtPct(v)}`}
                    >
                      {v === null ? "·" : fmtPct(v, 1, false)}
                    </div>
                  </td>
                ))}
                <td
                  className={cn(
                    "mono py-px pl-2 text-right text-[11px] font-medium",
                    annual === null
                      ? "text-text-4"
                      : annual - 1 >= 0
                        ? "text-pos"
                        : "text-neg",
                  )}
                >
                  {annual === null ? "—" : fmtPct(annual - 1, 1)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function cellBg(v: number | null): string {
  if (v === null) return "transparent";
  const intensity = Math.min(1, Math.abs(v) / 0.09);
  return v >= 0
    ? `rgba(63,169,124,${0.06 + intensity * 0.3})`
    : `rgba(217,99,94,${0.06 + intensity * 0.3})`;
}

function cellFg(v: number | null): string {
  if (v === null) return "transparent";
  const intensity = Math.min(1, Math.abs(v) / 0.09);
  return intensity > 0.55 ? "#e8e9eb" : v >= 0 ? "#7fc7a4" : "#e0908d";
}
