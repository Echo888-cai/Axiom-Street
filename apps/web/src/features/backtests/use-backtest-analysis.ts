import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Backtest } from "@/lib/api";
import { chartColors } from "@/lib/chart-tokens";
import { filterEquityByPeriod } from "@/lib/utils";
import { labelDirection } from "@/lib/labels";
import type {
  EquityMarker,
  EquitySeries,
} from "@/components/charts/equity-curve";
import type { ExposurePoint } from "@/components/charts/exposure-chart";
import {
  dailyReturnsFromEquity,
  histogram,
  normalizeSeries,
  pairedDailyReturns,
  qqNormal,
  rollingBeta,
  rollingSharpe,
} from "@/lib/tearsheet";

export function useBacktestAnalysis({
  backtest,
  backtestId,
  compareId,
  period,
  normalized,
  showTrades,
}: {
  backtest?: Backtest;
  backtestId: string;
  compareId: string;
  period: "1M" | "3M" | "YTD" | "1Y" | "ALL";
  normalized: boolean;
  showTrades: boolean;
}) {
  const ready = backtest?.status === "COMPLETED";
  const metrics = useQuery({
    queryKey: ["metrics", backtestId],
    queryFn: () => api.getMetrics(backtestId),
    enabled: ready,
  });
  const equity = useQuery({
    queryKey: ["equity", backtestId],
    queryFn: () => api.getEquity(backtestId),
    enabled: ready,
  });
  const trades = useQuery({
    queryKey: ["trades", backtestId],
    queryFn: () => api.getTrades(backtestId),
    enabled: ready,
  });
  const monthly = useQuery({
    queryKey: ["monthly", backtestId],
    queryFn: () => api.getMonthlyReturns(backtestId),
    enabled: ready,
  });
  const timeSeries = useQuery({
    queryKey: ["time-series", backtestId],
    queryFn: () => api.getTimeSeries(backtestId),
    enabled: ready,
  });
  const pboQuery = useQuery({
    queryKey: ["validation", backtest?.strategy_id, "PBO"],
    queryFn: () =>
      api.listValidation({
        strategy_id: backtest?.strategy_id || "",
        kind: "PBO",
      }),
    enabled: ready && Boolean(backtest?.strategy_id),
  });
  const peers = useQuery({
    queryKey: ["backtests", backtest?.strategy_id, "COMPLETED"],
    queryFn: () =>
      api.listBacktests({
        strategy_id: backtest?.strategy_id || "",
        status: "COMPLETED",
      }),
    enabled: Boolean(backtest?.strategy_id),
  });
  const compareEquity = useQuery({
    queryKey: ["equity", compareId],
    queryFn: () => api.getEquity(compareId),
    enabled: Boolean(compareId),
  });

  const pbo = useMemo(() => {
    const items = pboQuery.data?.items || [];
    const latest = items.find(
      (row) => row.status === "COMPLETED" && !row.error,
    );
    const value = latest?.result?.pbo;
    return typeof value === "number" ? value : null;
  }, [pboQuery.data]);

  const filteredEquity = useMemo(() => {
    const raw = (equity.data || []).map((p) => ({
      time: p.ts,
      strategy: p.strategy_value,
      benchmark: p.benchmark_value,
      drawdown: p.drawdown,
    }));
    return filterEquityByPeriod(raw, period);
  }, [equity.data, period]);

  const distribution = useMemo(() => {
    const values = (equity.data || []).map((p) => p.strategy_value);
    const benches = (equity.data || []).map((p) => p.benchmark_value);
    const times = (equity.data || []).slice(1).map((p) => p.ts);
    const daily = dailyReturnsFromEquity(values);
    if (daily.error) {
      return {
        error: daily.error,
        bins: [],
        qq: [],
        rolling: { points: [], error: daily.error },
        beta: { points: [], error: daily.error },
      };
    }
    const hist = histogram(daily.returns);
    const qq = qqNormal(daily.returns);
    const rolling = rollingSharpe(daily.returns, times);
    const paired = pairedDailyReturns(values, benches, times);
    const beta = paired.error
      ? { points: [], error: paired.error }
      : rollingBeta(paired.strategy, paired.benchmark, paired.times);
    return {
      error: hist.error || qq.error,
      bins: hist.bins,
      qq: qq.points,
      rolling,
      beta,
    };
  }, [equity.data]);

  const exposure = useMemo(() => {
    const rows = timeSeries.data || [];
    const byTime = new Map<string, ExposurePoint>();
    const turnover: { time: string; value: number }[] = [];
    for (const row of rows) {
      const time = row.ts;
      if (row.name === "turnover") {
        turnover.push({ time, value: row.value });
        continue;
      }
      const current = byTime.get(time) || { time };
      if (row.name === "exposure_long") current.long = row.value;
      if (row.name === "exposure_short") current.short = row.value;
      byTime.set(time, current);
    }
    const points = [...byTime.values()]
      .map((p) => ({
        ...p,
        net:
          p.long != null || p.short != null
            ? (p.long || 0) - (p.short || 0)
            : undefined,
      }))
      .sort((a, b) => a.time.localeCompare(b.time));
    return { points, turnover };
  }, [timeSeries.data]);

  const canLog = filteredEquity.every((p) => p.strategy > 0);
  const series: EquitySeries[] = useMemo(() => {
    const strategyValues = filteredEquity.map((p) => p.strategy);
    const benchValues = filteredEquity.map((p) => p.benchmark);
    const strategyNorm = normalized
      ? normalizeSeries(strategyValues)
      : { values: strategyValues };
    const out: EquitySeries[] = [
      {
        id: "strategy",
        label: normalized ? "本回测（=100）" : "本回测",
        color: chartColors.primary,
        data: filteredEquity.map((p, i) => ({
          time: p.time,
          value: strategyNorm.values[i] ?? p.strategy,
        })),
      },
    ];
    if (!normalized) {
      const benchPoints = filteredEquity
        .map((p) =>
          p.benchmark != null ? { time: p.time, value: p.benchmark } : null,
        )
        .filter((p): p is { time: string; value: number } => p != null);
      if (benchPoints.length) {
        out.push({
          id: "benchmark",
          label: "基准",
          color: chartColors.benchmark,
          dashed: true,
          data: benchPoints,
        });
      }
    } else {
      const aligned = benchValues
        .map((v, i) =>
          v != null && v > 0
            ? { time: filteredEquity[i].time, value: v }
            : null,
        )
        .filter((p): p is { time: string; value: number } => p != null);
      if (aligned.length) {
        const norm = normalizeSeries(aligned.map((p) => p.value));
        if (!norm.error) {
          out.push({
            id: "benchmark",
            label: "基准（=100）",
            color: chartColors.benchmark,
            dashed: true,
            data: aligned.map((p, i) => ({
              time: p.time,
              value: norm.values[i],
            })),
          });
        }
      }
    }
    if (compareId && compareEquity.data?.length) {
      const compareRaw = filterEquityByPeriod(
        compareEquity.data.map((p) => ({
          time: p.ts,
          strategy: p.strategy_value,
        })),
        period,
      );
      const source = compareRaw.map((p) => p.strategy);
      const scaled = normalized ? normalizeSeries(source) : { values: source };
      if (!scaled.error) {
        const peer = (peers.data || []).find((row) => row.id === compareId);
        out.push({
          id: "compare",
          label: peerLabel(peer, normalized),
          color: chartColors.positive,
          dashed: true,
          data: compareRaw.map((p, i) => ({
            time: p.time,
            value: scaled.values[i],
          })),
        });
      }
    }
    return out;
  }, [
    compareEquity.data,
    compareId,
    filteredEquity,
    normalized,
    peers.data,
    period,
  ]);

  const markers: EquityMarker[] = useMemo(() => {
    if (!showTrades) return [];
    return (trades.data || []).map((t) => {
      const buy = labelDirection(t.direction, t.quantity) !== "卖出";
      return {
        time: t.trade_date,
        label: t.ticker,
        buy,
      };
    });
  }, [showTrades, trades.data]);

  const drawdownPoints = useMemo(
    () =>
      (equity.data || []).map((p) => ({ time: p.ts, value: p.drawdown ?? 0 })),
    [equity.data],
  );

  return {
    metrics,
    equity,
    trades,
    monthly,
    timeSeries,
    peers,
    pbo,
    distribution,
    exposure,
    canLog,
    series,
    markers,
    drawdownPoints,
  };
}

export function peerLabel(row: Backtest | undefined, normalized: boolean): string {
  if (!row) return normalized ? "对比（=100）" : "对比";
  const range = `${row.start_date.slice(0, 10)} → ${row.end_date.slice(0, 10)}`;
  const version = row.version_number
    ? `v${row.version_number}`
    : row.id.slice(0, 8);
  return normalized ? `${version} ${range}（=100）` : `${version} ${range}`;
}
