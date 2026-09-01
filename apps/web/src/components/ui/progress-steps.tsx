import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export function ProgressSteps({
  steps,
  current,
}: {
  steps: string[];
  current: string | null;
}) {
  const idx = current ? steps.indexOf(current) : 0;
  const active = idx < 0 ? 0 : idx;
  return (
    <ol className="flex flex-wrap items-center gap-2">
      {steps.map((step, i) => {
        const done = i < active;
        const here = i === active;
        return (
          <li key={step} className="flex items-center gap-2">
            <span
              className={cn(
                "flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-medium",
                done && "bg-aq-positive text-white",
                here && "bg-aq-primary text-white",
                !done && !here && "bg-aq-secondary text-aq-muted",
              )}
            >
              {done ? <Check className="h-3 w-3" /> : i + 1}
            </span>
            <span className={cn("text-xs", here ? "font-medium text-aq-text" : "text-aq-muted")}>
              {step}
            </span>
            {i < steps.length - 1 ? (
              <span className="hidden h-px w-6 bg-aq-border sm:block" />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
