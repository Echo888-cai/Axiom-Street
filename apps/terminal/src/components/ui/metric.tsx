import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface MetricProps {
  label: string;
  value: string;
  tone?: "default" | "pos" | "neg" | "accent";
  hint?: string;
  className?: string;
}

const tones = {
  default: "text-text",
  pos: "text-pos",
  neg: "text-neg",
  accent: "text-accent",
};

/** Single figure: quiet label, mono tabular value. Never a giant card. */
export function Metric({ label, value, tone = "default", hint, className }: MetricProps) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-0.5", className)} title={hint}>
      <span className="text-[11px] leading-none text-text-3">{label}</span>
      <span className={cn("mono truncate text-[15px] leading-tight font-medium", tones[tone])}>
        {value}
      </span>
    </div>
  );
}

/**
 * The professional alternative to KPI cards: one continuous strip,
 * hairline dividers, Bloomberg-grade density.
 */
export function MetricStrip({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-stretch divide-x divide-edge rounded-lg border border-edge bg-panel",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function MetricCell({
  label,
  value,
  tone = "default",
  hint,
}: MetricProps) {
  return (
    <div className="flex min-w-0 flex-1 flex-col justify-center gap-1 px-3.5 py-2.5" title={hint}>
      <span className="text-[10.5px] leading-none tracking-wide text-text-3 uppercase">
        {label}
      </span>
      <span className={cn("mono truncate text-[15px] leading-tight font-medium", tones[tone])}>
        {value}
      </span>
    </div>
  );
}
