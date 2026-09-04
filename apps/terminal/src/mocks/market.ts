import { gaussian, hashSeed, mulberry32 } from "@/lib/prng";
import type { Candle, SymbolInfo } from "./types";
import { TRADING_DAYS } from "./engine";

export const SYMBOLS: SymbolInfo[] = [
  { symbol: "AAPL", name: "Apple Inc.", sector: "Technology", price: 232.14, changePct: 0.0118, marketCap: 3.42e12, pe: 31.2, eps: 7.44, revenue: 4.08e11, fcf: 1.12e11, roe: 1.51 },
  { symbol: "NVDA", name: "NVIDIA Corp.", sector: "Technology", price: 178.42, changePct: 0.0241, marketCap: 4.31e12, pe: 44.8, eps: 3.98, revenue: 1.86e11, fcf: 7.2e10, roe: 1.09 },
  { symbol: "MSFT", name: "Microsoft Corp.", sector: "Technology", price: 512.66, changePct: -0.0042, marketCap: 3.81e12, pe: 34.1, eps: 15.02, revenue: 2.82e11, fcf: 9.1e10, roe: 0.34 },
  { symbol: "META", name: "Meta Platforms", sector: "Communication", price: 742.9, changePct: 0.0087, marketCap: 1.88e12, pe: 26.4, eps: 28.1, revenue: 1.79e11, fcf: 5.4e10, roe: 0.38 },
  { symbol: "AMZN", name: "Amazon.com Inc.", sector: "Consumer Disc.", price: 228.31, changePct: -0.0113, marketCap: 2.39e12, pe: 33.7, eps: 6.78, revenue: 6.7e11, fcf: 4.2e10, roe: 0.22 },
  { symbol: "GOOGL", name: "Alphabet Inc.", sector: "Communication", price: 214.08, changePct: 0.0061, marketCap: 2.61e12, pe: 22.9, eps: 9.35, revenue: 3.85e11, fcf: 7.4e10, roe: 0.32 },
  { symbol: "SPY", name: "SPDR S&P 500 ETF", sector: "Index", price: 648.22, changePct: 0.0044, marketCap: 6.1e11, pe: 24.6, eps: 26.3, revenue: 0, fcf: 0, roe: 0 },
  { symbol: "QQQ", name: "Invesco QQQ Trust", sector: "Index", price: 578.94, changePct: 0.0092, marketCap: 3.2e11, pe: 29.8, eps: 19.4, revenue: 0, fcf: 0, roe: 0 },
];

export function getSymbol(sym: string): SymbolInfo {
  return SYMBOLS.find((s) => s.symbol === sym) ?? SYMBOLS[0];
}

const candleCache = new Map<string, Candle[]>();

/** Daily candles for a symbol, ~2 years, anchored near its listed price. */
export function getCandles(sym: string, days = 500): Candle[] {
  const key = `${sym}:${days}`;
  const hit = candleCache.get(key);
  if (hit) return hit;

  const info = getSymbol(sym);
  const rand = gaussian(mulberry32(hashSeed(`axiom/candles/${sym}`)));
  const drift = 0.0004 + (hashSeed(sym) % 100) / 100000;
  const vol = sym === "SPY" || sym === "QQQ" ? 0.009 : 0.016;

  const dates = TRADING_DAYS.slice(-days);
  // Walk backwards from the current price so the series ends at `info.price`
  const closes: number[] = new Array(days);
  closes[days - 1] = info.price;
  for (let i = days - 2; i >= 0; i--) {
    const r = drift + vol * rand();
    closes[i] = closes[i + 1] / (1 + r);
  }

  const candles: Candle[] = dates.map((t, i) => {
    const c = closes[i];
    const prev = i > 0 ? closes[i - 1] : c / (1 + drift);
    const spread = Math.abs(vol * rand()) * 0.8;
    const o = prev;
    const hi = Math.max(o, c) * (1 + spread * 0.6);
    const lo = Math.min(o, c) * (1 - spread * 0.6);
    return {
      t,
      o: round2(o),
      h: round2(hi),
      l: round2(lo),
      c: round2(c),
      vol: Math.round(2e7 + Math.abs(rand()) * 6e7),
    };
  });

  candleCache.set(key, candles);
  return candles;
}

function round2(v: number) {
  return Math.round(v * 100) / 100;
}
