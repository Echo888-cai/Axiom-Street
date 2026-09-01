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

type Point = {
  time: string;
  strategy: number;
  benchmark?: number | null;
};

export function EquityCurve({
  data,
  height = 280,
}: {
  data: Point[];
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const strategyRef = useRef<ISeriesApi<"Line"> | null>(null);
  const benchRef = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
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
      crosshair: {
        vertLine: { color: "rgba(22,119,255,0.25)", labelBackgroundColor: "#1677FF" },
        horzLine: { color: "rgba(22,119,255,0.25)", labelBackgroundColor: "#1677FF" },
      },
    });

    const strategy = chart.addSeries(LineSeries, {
      color: "#1677FF",
      lineWidth: 2,
      priceLineVisible: false,
    });
    const bench = chart.addSeries(LineSeries, {
      color: "#98A2B3",
      lineWidth: 2,
      priceLineVisible: false,
    });

    chartRef.current = chart;
    strategyRef.current = strategy;
    benchRef.current = bench;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [height]);

  useEffect(() => {
    if (!strategyRef.current || !benchRef.current) return;
    const strategyData: LineData[] = data.map((d) => ({
      time: d.time.slice(0, 10) as LineData["time"],
      value: d.strategy,
    }));
    const benchData: LineData[] = data
      .filter((d) => d.benchmark != null)
      .map((d) => ({
        time: d.time.slice(0, 10) as LineData["time"],
        value: d.benchmark as number,
      }));
    strategyRef.current.setData(strategyData);
    benchRef.current.setData(benchData);
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return (
    <div>
      <div ref={containerRef} className="w-full" />
      <div className="mt-2 flex items-center justify-between gap-3 text-[10px] text-aq-muted">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-3 rounded-full bg-aq-primary" />
            策略
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-3 rounded-full bg-[#98A2B3]" />
            基准
          </span>
        </div>
        <span>图表：TradingView Lightweight Charts（Apache-2.0）</span>
      </div>
    </div>
  );
}
