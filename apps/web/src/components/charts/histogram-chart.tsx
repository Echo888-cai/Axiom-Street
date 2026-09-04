"use client";

import type { HistogramBin } from "@/lib/tearsheet";
import { formatPct } from "@/lib/utils";

export function HistogramChart({ bins }: { bins: HistogramBin[] }) {
  const max = Math.max(...bins.map((b) => b.count), 1);
  const zero = bins.findIndex((b) => b.x0 <= 0 && b.x1 >= 0);

  return (
    <div>
      <div className="flex h-48 items-end gap-px">
        {bins.map((bin, i) => (
          <div
            key={`${bin.x0}-${bin.x1}`}
            className="group relative flex min-w-0 flex-1 flex-col justify-end"
            title={`${formatPct(bin.x0)} – ${formatPct(bin.x1)} · ${bin.count} 天`}
          >
            <div
              className={`w-full rounded-t-[2px] transition-colors duration-as ${
                i === zero ? "bg-as-text/40" : bin.x1 <= 0 ? "bg-as-negative/70" : "bg-as-primary/80"
              }`}
              style={{ height: `${(bin.count / max) * 100}%`, minHeight: bin.count ? 2 : 0 }}
            />
          </div>
        ))}
      </div>
      <div className="mt-2 flex justify-between text-[10px] tabular text-as-muted">
        <span>{formatPct(bins[0]?.x0)}</span>
        <span>0</span>
        <span>{formatPct(bins[bins.length - 1]?.x1)}</span>
      </div>
    </div>
  );
}
