import {
  CandlestickSeries,
  HistogramSeries,
  type CandlestickData,
  type HistogramData,
  type Time,
} from "lightweight-charts";
import type { Candle } from "@/mocks/types";
import { COLORS, useChart } from "./use-chart";

/** TradingView-grade candlestick panel with volume, quiet terminal palette. */
export function PriceChart({ candles }: { candles: Candle[] }) {
  const containerRef = useChart(
    (chart) => {
      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: COLORS.pos,
        downColor: COLORS.neg,
        wickUpColor: COLORS.pos,
        wickDownColor: COLORS.neg,
        borderVisible: false,
        priceLineColor: "rgba(232,233,235,0.3)",
      });
      const candleData: CandlestickData<Time>[] = candles.map((c) => ({
        time: c.t as Time,
        open: c.o,
        high: c.h,
        low: c.l,
        close: c.c,
      }));
      candleSeries.setData(candleData);

      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceScaleId: "vol",
        priceFormat: { type: "volume" },
      });
      chart.priceScale("vol").applyOptions({
        scaleMargins: { top: 0.82, bottom: 0 },
      });
      const volumeData: HistogramData<Time>[] = candles.map((c) => ({
        time: c.t as Time,
        value: c.vol,
        color: c.c >= c.o ? "rgba(63,169,124,0.28)" : "rgba(217,99,94,0.28)",
      }));
      volumeSeries.setData(volumeData);
    },
    [candles],
    { rightPriceScale: { borderColor: "rgba(255,255,255,0.07)" } },
  );

  return <div ref={containerRef} className="h-full w-full" />;
}
