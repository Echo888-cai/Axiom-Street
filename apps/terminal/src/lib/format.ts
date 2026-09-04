/**
 * Financial formatting — the terminal never shows a raw number.
 * All figures render in JetBrains Mono with tabular-nums.
 */

export function fmtPct(v: number, digits = 2, signed = true): string {
  const sign = signed && v > 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(digits)}%`;
}

export function fmtNum(v: number, digits = 2, signed = false): string {
  const sign = signed && v > 0 ? "+" : "";
  return `${sign}${v.toFixed(digits)}`;
}

export function fmtCurrency(v: number, digits = 0, signed = false): string {
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : signed ? "+" : "";
  const body = abs.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return `${sign}$${body}`;
}

/** $12.4M / $842K / $12,841 */
export function fmtCompact(v: number, signed = false): string {
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : signed ? "+" : "";
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 10_000) return `${sign}$${(abs / 1_000).toFixed(1)}K`;
  return `${sign}$${abs.toLocaleString("en-US")}`;
}

export function fmtDate(d: string | Date): string {
  const date = typeof d === "string" ? new Date(d) : d;
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function fmtDateShort(d: string | Date): string {
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function fmtDuration(ms: number): string {
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

export function fmtTime(d: string | Date): string {
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}
