"use client";
import { chartColors } from "@/lib/chart-tokens";

import { useEffect, useRef } from "react";
import {
  AreaSeries,
  ColorType,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type AreaData,
} from "lightweight-charts";

export function DrawdownChart({
  data,
  height = 180,
}: {
  data: { time: string; value: number }[];
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: chartColors.background },
        textColor: chartColors.muted,
      },
      grid: {
        vertLines: { color: chartColors.grid },
        horzLines: { color: chartColors.grid },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    const series = chart.addSeries(AreaSeries, {
      lineColor: chartColors.negative,
      topColor: chartColors.negativeArea,
      bottomColor: chartColors.negativeFade,
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
  }, [height]);

  useEffect(() => {
    if (!seriesRef.current) return;
    const points: AreaData[] = data.map((d) => ({
      time: d.time.slice(0, 10) as AreaData["time"],
      value: d.value * 100,
    }));
    seriesRef.current.setData(points);
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return <div ref={ref} className="w-full" />;
}
