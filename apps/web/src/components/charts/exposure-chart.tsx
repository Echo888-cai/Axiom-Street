"use client";
import { chartColors } from "@/lib/chart-tokens";

import { useEffect, useRef } from "react";
import {
  ColorType,
  createChart,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type LineData,
} from "lightweight-charts";

export type ExposurePoint = {
  time: string;
  long?: number;
  short?: number;
  net?: number;
  turnover?: number;
};

export function ExposureChart({
  data,
  height = 220,
}: {
  data: ExposurePoint[];
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const longRef = useRef<ISeriesApi<"Line"> | null>(null);
  const shortRef = useRef<ISeriesApi<"Line"> | null>(null);
  const netRef = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: chartColors.background },
        textColor: chartColors.muted,
        fontFamily: "Inter, system-ui, sans-serif",
      },
      grid: {
        vertLines: { color: chartColors.grid },
        horzLines: { color: chartColors.grid },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    longRef.current = chart.addSeries(LineSeries, {
      color: chartColors.primary,
      lineWidth: 2,
      priceLineVisible: false,
      title: "多头",
    });
    shortRef.current = chart.addSeries(LineSeries, {
      color: chartColors.negative,
      lineWidth: 2,
      priceLineVisible: false,
      title: "空头",
    });
    netRef.current = chart.addSeries(LineSeries, {
      color: chartColors.muted,
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      title: "净暴露",
    });
    chartRef.current = chart;
    const ro = new ResizeObserver(() => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth });
    });
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [height]);

  useEffect(() => {
    const toLine = (key: "long" | "short" | "net"): LineData[] =>
      data
        .filter((d) => d[key] != null)
        .map((d) => ({
          time: d.time.slice(0, 10) as LineData["time"],
          value: d[key] as number,
        }));
    longRef.current?.setData(toLine("long"));
    shortRef.current?.setData(toLine("short"));
    netRef.current?.setData(toLine("net"));
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return (
    <div>
      <div ref={ref} className="w-full" />
      <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-as-muted">
        <span className="inline-flex items-center gap-1">
          <span className="h-0.5 w-3 bg-as-primary" /> 多头
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-0.5 w-3 bg-[#F04438]" /> 空头
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-0.5 w-3 bg-as-muted" /> 净暴露
        </span>
      </div>
    </div>
  );
}
