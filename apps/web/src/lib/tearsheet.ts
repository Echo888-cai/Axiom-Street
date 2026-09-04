export type HistogramBin = {
  x0: number;
  x1: number;
  count: number;
};

export type RollingPoint = {
  time: string;
  sharpe: number;
  volatility: number;
  beta?: number;
  correlation?: number;
};

export type SeriesPoint = {
  time: string;
  value: number;
};

export type QqPoint = {
  theoretical: number;
  sample: number;
};

export function dailyReturnsFromEquity(values: number[]): { returns: number[]; error?: string } {
  if (values.length < 2) {
    return { returns: [], error: "权益序列不足 2 点，无法计算日收益" };
  }
  const returns: number[] = [];
  for (let i = 1; i < values.length; i += 1) {
    const prev = values[i - 1];
    const cur = values[i];
    if (!(prev > 0) || !(cur > 0)) {
      return { returns: [], error: "权益序列含非正值，无法计算收益" };
    }
    returns.push(cur / prev - 1);
  }
  return { returns };
}

export function normalizeSeries(values: number[], base = 100): { values: number[]; error?: string } {
  if (!values.length) return { values: [], error: "序列为空，无法归一化" };
  const first = values[0];
  if (!(first > 0)) return { values: [], error: "序列起点非正，无法归一化" };
  return { values: values.map((v) => (v / first) * base) };
}

export function rollingSharpe(
  returns: number[],
  times: string[],
  window = 63,
  periodsPerYear = 252,
): { points: RollingPoint[]; error?: string } {
  if (window < 2) return { points: [], error: "滚动窗口过短" };
  if (returns.length !== times.length) {
    return { points: [], error: "收益与时间戳长度不一致" };
  }
  if (returns.length < window) {
    return { points: [], error: `权益序列不足 ${window} 根，无法计算滚动夏普` };
  }
  const points: RollingPoint[] = [];
  for (let end = window; end <= returns.length; end += 1) {
    const slice = returns.slice(end - window, end);
    const mean = slice.reduce((s, r) => s + r, 0) / window;
    let varSum = 0;
    for (const r of slice) {
      const d = r - mean;
      varSum += d * d;
    }
    const std = Math.sqrt(varSum / (window - 1));
    if (std === 0) continue;
    points.push({
      time: times[end - 1],
      sharpe: (mean / std) * Math.sqrt(periodsPerYear),
      volatility: std * Math.sqrt(periodsPerYear),
    });
  }
  if (!points.length) {
    return { points: [], error: "滚动窗口内收益没有波动，无法计算夏普" };
  }
  return { points };
}

export function pairedDailyReturns(
  strategy: number[],
  benchmark: Array<number | null | undefined>,
  times: string[],
): { strategy: number[]; benchmark: number[]; times: string[]; error?: string } {
  if (strategy.length !== benchmark.length) {
    return { strategy: [], benchmark: [], times: [], error: "策略与基准净值长度不一致" };
  }
  if (times.length && times.length !== strategy.length - 1 && times.length !== strategy.length) {
    return { strategy: [], benchmark: [], times: [], error: "时间戳与净值长度不一致" };
  }
  if (strategy.length < 2) {
    return { strategy: [], benchmark: [], times: [], error: "权益序列不足 2 点，无法计算配对收益" };
  }
  const sR: number[] = [];
  const bR: number[] = [];
  const tS: string[] = [];
  for (let i = 1; i < strategy.length; i += 1) {
    const s0 = strategy[i - 1];
    const s1 = strategy[i];
    const b0 = benchmark[i - 1];
    const b1 = benchmark[i];
    if (!(s0 > 0) || !(s1 > 0)) {
      return { strategy: [], benchmark: [], times: [], error: "权益序列含非正值，无法计算收益" };
    }
    if (b0 == null || b1 == null || !(b0 > 0) || !(b1 > 0)) continue;
    sR.push(s1 / s0 - 1);
    bR.push(b1 / b0 - 1);
    tS.push(times[i - 1] ?? times[i] ?? "");
  }
  if (!sR.length) {
    return { strategy: [], benchmark: [], times: [], error: "没有可用的基准净值，无法计算滚动 β" };
  }
  return { strategy: sR, benchmark: bR, times: tS };
}

export function rollingBeta(
  strategyReturns: number[],
  benchmarkReturns: number[],
  times: string[],
  window = 63,
): { points: RollingPoint[]; error?: string } {
  if (window < 2) return { points: [], error: "滚动窗口过短" };
  if (strategyReturns.length !== benchmarkReturns.length || strategyReturns.length !== times.length) {
    return { points: [], error: "收益、基准与时间戳长度不一致" };
  }
  if (strategyReturns.length < window) {
    return { points: [], error: `配对收益不足 ${window} 根，无法计算滚动 β` };
  }
  const points: RollingPoint[] = [];
  for (let end = window; end <= strategyReturns.length; end += 1) {
    const ys = strategyReturns.slice(end - window, end);
    const xs = benchmarkReturns.slice(end - window, end);
    const meanY = ys.reduce((s, r) => s + r, 0) / window;
    const meanX = xs.reduce((s, r) => s + r, 0) / window;
    let cov = 0;
    let varX = 0;
    let varY = 0;
    for (let i = 0; i < window; i += 1) {
      const dy = ys[i] - meanY;
      const dx = xs[i] - meanX;
      cov += dx * dy;
      varX += dx * dx;
      varY += dy * dy;
    }
    cov /= window - 1;
    varX /= window - 1;
    varY /= window - 1;
    if (varX === 0) continue;
    const stdX = Math.sqrt(varX);
    const stdY = Math.sqrt(varY);
    points.push({
      time: times[end - 1],
      sharpe: 0,
      volatility: stdY * Math.sqrt(252),
      beta: cov / varX,
      correlation: stdY === 0 ? undefined : cov / (stdX * stdY),
    });
  }
  if (!points.length) {
    return { points: [], error: "滚动窗口内基准没有波动，无法计算 β" };
  }
  return { points };
}

export function histogram(returns: number[], binCount = 21): { bins: HistogramBin[]; error?: string } {
  if (returns.length < 5) {
    return { bins: [], error: "日收益不足 5 个，无法画分布" };
  }
  if (binCount < 2) return { bins: [], error: "分箱数过少" };
  let min = returns[0];
  let max = returns[0];
  for (const r of returns) {
    if (r < min) min = r;
    if (r > max) max = r;
  }
  if (min === max) {
    return { bins: [], error: "日收益无变化，无法画分布" };
  }
  const width = (max - min) / binCount;
  const bins: HistogramBin[] = Array.from({ length: binCount }, (_, i) => ({
    x0: min + i * width,
    x1: min + (i + 1) * width,
    count: 0,
  }));
  for (const r of returns) {
    let idx = Math.floor((r - min) / width);
    if (idx === binCount) idx = binCount - 1;
    bins[idx].count += 1;
  }
  return { bins };
}

/** Acklam rational approximation of the standard normal quantile. */
export function inverseNormalCdf(p: number): number {
  if (!(p > 0) || !(p < 1)) {
    throw new Error("inverseNormalCdf 只接受 (0, 1) 开区间");
  }
  const a = [
    -3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2, 1.383577509590705e2,
    -3.066479806614716e1, 2.506628277459239,
  ];
  const b = [
    -5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2, 6.680131188771972e1,
    -1.328068155288572e1,
  ];
  const c = [
    -7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838, -2.549732539343734,
    4.374664141464968, 2.938163982698783,
  ];
  const d = [7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996, 3.754408661907416];
  const plow = 0.02425;
  const phigh = 1 - plow;
  if (p < plow) {
    const q = Math.sqrt(-2 * Math.log(p));
    return (
      (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
      ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    );
  }
  if (p > phigh) {
    const q = Math.sqrt(-2 * Math.log(1 - p));
    return -(
      (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
      ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    );
  }
  const q = p - 0.5;
  const r = q * q;
  return (
    ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) /
    (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
  );
}

export function qqNormal(returns: number[]): { points: QqPoint[]; error?: string } {
  if (returns.length < 5) {
    return { points: [], error: "日收益不足 5 个，无法画 QQ 图" };
  }
  const sorted = [...returns].sort((a, b) => a - b);
  const n = sorted.length;
  const points: QqPoint[] = sorted.map((sample, i) => ({
    theoretical: inverseNormalCdf((i + 0.5) / n),
    sample,
  }));
  return { points };
}
