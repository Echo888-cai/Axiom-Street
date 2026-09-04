import { useEffect, useRef } from "react";
import {
  ColorType,
  CrosshairMode,
  createChart,
  type IChartApi,
  type DeepPartial,
  type ChartOptions,
} from "lightweight-charts";

export const CHART_THEME: DeepPartial<ChartOptions> = {
  layout: {
    background: { type: ColorType.Solid, color: "transparent" },
    textColor: "#5f656d",
    fontFamily: "'JetBrains Mono Variable', ui-monospace, monospace",
    fontSize: 10,
    attributionLogo: false,
  },
  grid: {
    vertLines: { color: "rgba(255,255,255,0.035)" },
    horzLines: { color: "rgba(255,255,255,0.035)" },
  },
  rightPriceScale: {
    borderColor: "rgba(255,255,255,0.07)",
  },
  timeScale: {
    borderColor: "rgba(255,255,255,0.07)",
    timeVisible: false,
    fixLeftEdge: true,
    fixRightEdge: true,
  },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: {
      color: "rgba(232,233,235,0.25)",
      labelBackgroundColor: "#1c1f24",
    },
    horzLine: {
      color: "rgba(232,233,235,0.25)",
      labelBackgroundColor: "#1c1f24",
    },
  },
};

export const COLORS = {
  accent: "#e3b341",
  pos: "#3fa97c",
  neg: "#d9635e",
  bench: "#6b7280",
  info: "#7fa6e8",
  text3: "#5f656d",
} as const;

/**
 * Own the chart in a single effect. Never call removeSeries after
 * chart.remove() — StrictMode double-mounts will throw "Value is undefined".
 */
export function useChart(
  setup: (chart: IChartApi) => void,
  deps: unknown[],
  overrides?: DeepPartial<ChartOptions>,
) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      ...CHART_THEME,
      ...overrides,
      width: Math.max(el.clientWidth, 1),
      height: Math.max(el.clientHeight, 1),
    });
    setup(chart);
    chart.timeScale().fitContent();

    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) chart.applyOptions({ width, height });
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      chart.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return containerRef;
}
