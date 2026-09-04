"use client";

import { useEffect, useRef } from "react";
import {
  ColorType,
  createChart,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type LineData,
} from "lightweight-charts";
import type { SeriesPoint } from "@/lib/tearsheet";

export function RollingChart({
  data,
  color = "#1677FF",
  caption,
  height = 180,
}: {
  data: SeriesPoint[];
  color?: string;
  caption?: string;
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#667085",
        fontFamily: "Inter, system-ui, sans-serif",
      },
      grid: {
        vertLines: { color: "rgba(15,23,42,0.04)" },
        horzLines: { color: "rgba(15,23,42,0.04)" },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    const series = chart.addSeries(LineSeries, {
      color,
      lineWidth: 2,
      priceLineVisible: false,
    });
    chartRef.current = chart;
    seriesRef.current = series;
    const ro = new ResizeObserver(() => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth });
    });
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [color, height]);

  useEffect(() => {
    if (!seriesRef.current) return;
    seriesRef.current.setData(
      data.map((d) => ({
        time: d.time.slice(0, 10) as LineData["time"],
        value: d.value,
      })),
    );
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return (
    <div>
      <div ref={ref} className="w-full" />
      {caption ? <div className="mt-2 text-[10px] text-as-muted">{caption}</div> : null}
    </div>
  );
}
