"use client";

import { useEffect, useRef } from "react";
import {
  ColorType,
  LineStyle,
  PriceScaleMode,
  createChart,
  createSeriesMarkers,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type Time,
} from "lightweight-charts";

export type EquitySeries = {
  id: string;
  label: string;
  color: string;
  dashed?: boolean;
  data: { time: string; value: number }[];
};

export type EquityMarker = {
  time: string;
  label: string;
  buy: boolean;
};

type LegacyPoint = {
  time: string;
  strategy: number;
  benchmark?: number | null;
};

function fromLegacy(data: LegacyPoint[]): EquitySeries[] {
  const series: EquitySeries[] = [
    {
      id: "strategy",
      label: "策略",
      color: "#1677FF",
      data: data.map((d) => ({ time: d.time, value: d.strategy })),
    },
  ];
  const bench = data.filter((d) => d.benchmark != null);
  if (bench.length) {
    series.push({
      id: "benchmark",
      label: "基准",
      color: "#98A2B3",
      dashed: true,
      data: bench.map((d) => ({ time: d.time, value: d.benchmark as number })),
    });
  }
  return series;
}

export function EquityCurve({
  data,
  series,
  logScale = false,
  markers = [],
  height = 320,
}: {
  data?: LegacyPoint[];
  series?: EquitySeries[];
  logScale?: boolean;
  markers?: EquityMarker[];
  height?: number;
}) {
  const resolved = series ?? fromLegacy(data || []);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRefs = useRef<ISeriesApi<"Line">[]>([]);

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
      rightPriceScale: {
        borderVisible: false,
        mode: logScale ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
      },
      timeScale: { borderVisible: false },
      crosshair: {
        vertLine: { color: "rgba(22,119,255,0.25)", labelBackgroundColor: "#1677FF" },
        horzLine: { color: "rgba(22,119,255,0.25)", labelBackgroundColor: "#1677FF" },
      },
    });

    const created = resolved.map((item) =>
      chart.addSeries(LineSeries, {
        color: item.color,
        lineWidth: 2,
        lineStyle: item.dashed ? LineStyle.Dashed : LineStyle.Solid,
        priceLineVisible: false,
          lastValueVisible: resolved.length > 1,
      }),
    );

    chartRef.current = chart;
    seriesRefs.current = created;

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
      seriesRefs.current = [];
    };
  }, [height, logScale, resolved.map((s) => `${s.id}:${s.dashed ? "d" : "s"}:${s.color}`).join("|")]);

  useEffect(() => {
    const apis = seriesRefs.current;
    resolved.forEach((item, i) => {
      const api = apis[i];
      if (!api) return;
      const points: LineData[] = item.data.map((d) => ({
        time: d.time.slice(0, 10) as LineData["time"],
        value: d.value,
      }));
      api.setData(points);
    });
    if (apis[0]) {
      createSeriesMarkers(
        apis[0],
        markers.length
          ? markers.map((m) => ({
              time: m.time.slice(0, 10) as Time,
              position: m.buy ? "belowBar" : "aboveBar",
              color: m.buy ? "#12B76A" : "#F04438",
              shape: m.buy ? "arrowUp" : "arrowDown",
              text: m.label,
            }))
          : [],
      );
    }
    chartRef.current?.timeScale().fitContent();
  }, [resolved, markers]);

  return (
    <div>
      <div ref={containerRef} className="w-full" />
      <div className="mt-2 flex flex-wrap items-center justify-between gap-3 text-[10px] text-as-muted">
        <div className="flex flex-wrap items-center gap-3">
          {resolved.map((item) => (
            <span key={item.id} className="inline-flex items-center gap-1.5">
              <span
                className="h-1.5 w-4 rounded-full"
                style={{
                  background: item.dashed
                    ? "repeating-linear-gradient(90deg, transparent, transparent 2px, currentColor 2px, currentColor 5px)"
                    : item.color,
                  color: item.color,
                  backgroundColor: item.dashed ? "transparent" : item.color,
                  borderBottom: item.dashed ? `1.5px dashed ${item.color}` : undefined,
                }}
              />
              {item.label}
            </span>
          ))}
        </div>
        <span>图表：TradingView Lightweight Charts（Apache-2.0）</span>
      </div>
    </div>
  );
}
