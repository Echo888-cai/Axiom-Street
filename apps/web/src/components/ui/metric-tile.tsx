import { cn } from "@/lib/utils";

export function MetricTile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "pos" | "neg" | "neutral";
}) {
  return (
    <div className="rounded-aq border border-aq-border bg-aq-bg px-3.5 py-3 transition-colors duration-aq hover:border-aq-primary/20">
      <div className="text-[11px] text-aq-muted">{label}</div>
      <div
        className={cn(
          "mt-1.5 text-[15px] font-semibold tabular tracking-tight",
          tone === "pos" && "text-aq-positive",
          tone === "neg" && "text-aq-negative",
          (!tone || tone === "neutral") && "text-aq-text",
        )}
      >
        {value}
      </div>
      {hint ? <div className="mt-1 text-[10px] text-aq-muted">{hint}</div> : null}
    </div>
  );
}

export function metricTone(value: number | null | undefined): "pos" | "neg" | undefined {
  if (value == null || Number.isNaN(value) || value === 0) return undefined;
  return value > 0 ? "pos" : "neg";
}
