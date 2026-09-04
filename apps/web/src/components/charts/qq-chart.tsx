"use client";

import { useMemo } from "react";
import type { QqPoint } from "@/lib/tearsheet";

export function QqChart({ points }: { points: QqPoint[] }) {
  const box = 220;
  const pad = 18;
  const inner = box - pad * 2;

  const geometry = useMemo(() => {
    const xs = points.map((p) => p.theoretical);
    const ys = points.map((p) => p.sample);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const spanX = maxX - minX || 1;
    const spanY = maxY - minY || 1;
    const toX = (v: number) => pad + ((v - minX) / spanX) * inner;
    const toY = (v: number) => pad + (1 - (v - minY) / spanY) * inner;
    const refMin = Math.min(minX, minY);
    const refMax = Math.max(maxX, maxY);
    return {
      dots: points.map((p) => ({ x: toX(p.theoretical), y: toY(p.sample) })),
      ref: {
        x1: toX(refMin),
        y1: toY(refMin),
        x2: toX(refMax),
        y2: toY(refMax),
      },
    };
  }, [inner, points]);

  return (
    <svg viewBox={`0 0 ${box} ${box}`} className="h-48 w-full max-w-[280px] text-as-muted">
      <line
        x1={geometry.ref.x1}
        y1={geometry.ref.y1}
        x2={geometry.ref.x2}
        y2={geometry.ref.y2}
        stroke="currentColor"
        strokeDasharray="4 3"
        strokeWidth="1"
      />
      {geometry.dots.map((d, i) => (
        <circle key={`${d.x}-${d.y}-${i}`} cx={d.x} cy={d.y} r="2.2" fill="#1677FF" />
      ))}
    </svg>
  );
}
