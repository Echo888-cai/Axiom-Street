import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPct(
  value: number | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
}

export function formatNumber(
  value: number | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatUsd(
  value: number | null | undefined,
  digits = 0,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) return "—";
  // The database emits naive UTC; do not interpret it in the browser timezone.
  const timestamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(
    value,
  )
    ? `${value}Z`
    : value;
  const then = new Date(timestamp).getTime();
  if (Number.isNaN(then)) return "—";
  const delta = Date.now() - then;
  const minutes = Math.floor(delta / 60000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "昨天";
  if (days < 7) return `${days} 天前`;
  return formatDate(value);
}

export function filterEquityByPeriod<T extends { time: string }>(
  data: T[],
  period: "1D" | "1M" | "3M" | "YTD" | "1Y" | "ALL",
): T[] {
  if (!data.length || period === "ALL") return data;
  const last = new Date(data[data.length - 1].time);
  const start = new Date(last);
  if (period === "1D") start.setDate(last.getDate() - 1);
  if (period === "1M") start.setMonth(last.getMonth() - 1);
  if (period === "3M") start.setMonth(last.getMonth() - 3);
  if (period === "1Y") start.setFullYear(last.getFullYear() - 1);
  if (period === "YTD") start.setMonth(0, 1);
  return data.filter((d) => new Date(d.time) >= start);
}
