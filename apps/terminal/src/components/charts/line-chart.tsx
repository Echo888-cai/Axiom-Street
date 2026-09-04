import {
  AreaSeries,
  LineSeries,
  type LineData,
  type Time,
} from "lightweight-charts";
import type { SeriesPoint } from "@/mocks/types";
import { COLORS, useChart } from "./use-chart";

export interface LineSeriesSpec {
  data: SeriesPoint[];
  color: string;
  /** area fill under the line */
  area?: boolean;
  lineWidth?: 1 | 2;
  dashed?: boolean;
  dotted?: boolean;
  priceLine?: boolean;
}

/**
 * Multi-series line/area chart — equity curves, drawdowns, rolling stats.
 * Strategy line takes the accent; benchmarks stay quiet gray.
 */
export function LineChart({
  series,
  height,
  baseline,
}: {
  series: LineSeriesSpec[];
  height?: number;
  /** render values as % deviation from first point (drawdown mode) */
  baseline?: boolean;
}) {
  const seriesKey = series
    .map(
      (s) =>
        `${s.color}:${s.area ? 1 : 0}:${s.dashed ? 1 : 0}:${s.dotted ? 1 : 0}:${s.data.length}:${s.data[0]?.t}:${s.data[s.data.length - 1]?.v}`,
    )
    .join("|");

  const containerRef = useChart(
    (chart) => {
      for (const spec of series) {
        const api = spec.area
          ? chart.addSeries(AreaSeries, {
              lineColor: spec.color,
              topColor: hexA(spec.color, 0.16),
              bottomColor: hexA(spec.color, 0.0),
              lineWidth: spec.lineWidth ?? 2,
              priceLineVisible: spec.priceLine ?? false,
              crosshairMarkerRadius: 3,
              crosshairMarkerBorderColor: spec.color,
              crosshairMarkerBackgroundColor: "#0a0a0b",
            })
          : chart.addSeries(LineSeries, {
              color: spec.color,
              lineWidth: spec.lineWidth ?? 1,
              lineStyle: spec.dotted ? 1 : spec.dashed ? 2 : 0,
              priceLineVisible: false,
              crosshairMarkerRadius: 3,
            });
        const data: LineData<Time>[] = spec.data.map((p) => ({
          time: p.t as Time,
          value: p.v,
        }));
        api.setData(data);
      }
    },
    [seriesKey, baseline],
    baseline
      ? {
          rightPriceScale: {
            borderColor: "rgba(255,255,255,0.07)",
          },
          localization: {
            priceFormatter: (v: number) => `${(v * 100).toFixed(1)}%`,
          },
        }
      : undefined,
  );

  return (
    <div
      ref={containerRef}
      className="h-full w-full"
      style={height ? { height } : undefined}
    />
  );
}

function hexA(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

export { COLORS };
