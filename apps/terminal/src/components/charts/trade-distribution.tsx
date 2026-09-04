import { useMemo } from "react";
import { fmtPct } from "@/lib/format";
import type { Trade } from "@/mocks/types";

const BINS = 21;
const RANGE = 0.07; // ±7%

/** Trade P&L distribution — pure SVG, zero dependencies. */
export function TradeDistribution({ trades }: { trades: Trade[] }) {
  const { bins, max, mean, median } = useMemo(() => {
    const bins = new Array(BINS).fill(0) as number[];
    for (const t of trades) {
      const clamped = Math.max(-RANGE, Math.min(RANGE, t.pnlPct));
      const idx = Math.min(BINS - 1, Math.floor(((clamped + RANGE) / (2 * RANGE)) * BINS));
      bins[idx]++;
    }
    const sorted = [...trades].sort((a, b) => a.pnlPct - b.pnlPct);
    const mean = trades.reduce((a, t) => a + t.pnlPct, 0) / trades.length;
    const median = sorted[Math.floor(sorted.length / 2)]?.pnlPct ?? 0;
    return { bins, max: Math.max(...bins), mean, median };
  }, [trades]);

  const W = 560;
  const H = 120;
  const bw = W / BINS;
  const zeroX = W / 2;

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H + 18}`} className="w-full">
        {/* zero line */}
        <line x1={zeroX} y1={4} x2={zeroX} y2={H} stroke="rgba(255,255,255,0.14)" strokeDasharray="3 3" />
        {bins.map((count, i) => {
          const h = max === 0 ? 0 : (count / max) * (H - 12);
          const center = -RANGE + ((i + 0.5) / BINS) * 2 * RANGE;
          const pos = center >= 0;
          return (
            <rect
              key={i}
              x={i * bw + 1}
              y={H - h}
              width={bw - 2}
              height={h}
              rx={1.5}
              fill={pos ? "rgba(63,169,124,0.55)" : "rgba(217,99,94,0.55)"}
            >
              <title>{`${fmtPct(center, 1, false)} · ${count} trades`}</title>
            </rect>
          );
        })}
        <text x={4} y={H + 13} className="fill-[#5f656d]" fontSize={9} fontFamily="JetBrains Mono Variable, monospace">
          −7%
        </text>
        <text x={zeroX} y={H + 13} textAnchor="middle" className="fill-[#5f656d]" fontSize={9} fontFamily="JetBrains Mono Variable, monospace">
          0
        </text>
        <text x={W - 4} y={H + 13} textAnchor="end" className="fill-[#5f656d]" fontSize={9} fontFamily="JetBrains Mono Variable, monospace">
          +7%
        </text>
      </svg>
      <div className="mono mt-1 flex items-center gap-4 px-1 text-[10.5px] text-text-3">
        <span>
          mean <span className={mean >= 0 ? "text-pos" : "text-neg"}>{fmtPct(mean)}</span>
        </span>
        <span>
          median <span className={median >= 0 ? "text-pos" : "text-neg"}>{fmtPct(median)}</span>
        </span>
        <span>
          n <span className="text-text-2">{trades.length}</span>
        </span>
      </div>
    </div>
  );
}
