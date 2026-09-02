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
    <div className="rounded-as border border-as-border bg-as-bg px-3.5 py-3 transition-colors duration-as hover:border-as-primary/20">
      <div className="text-[11px] text-as-muted">{label}</div>
      <div
        className={cn(
          "mt-1.5 text-[15px] font-semibold tabular tracking-tight",
          tone === "pos" && "text-as-positive",
          tone === "neg" && "text-as-negative",
          (!tone || tone === "neutral") && "text-as-text",
        )}
      >
        {value}
      </div>
      {hint ? <div className="mt-1 text-[10px] text-as-muted">{hint}</div> : null}
    </div>
  );
}

export function metricTone(value: number | null | undefined): "pos" | "neg" | undefined {
  if (value == null || Number.isNaN(value) || value === 0) return undefined;
  return value > 0 ? "pos" : "neg";
}
