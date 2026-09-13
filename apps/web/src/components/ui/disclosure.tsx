import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

/** Secondary context stays available without competing with the main task. */
export function Disclosure({ title, children, className, open }: {
  title: string;
  children: ReactNode;
  className?: string;
  open?: boolean;
}) {
  return (
    <details open={open} className={cn("as-disclosure group/disclosure rounded-2xl border border-as-border/70 bg-white/60", className)}>
      <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-xs font-medium text-as-muted hover:text-as-text">
        {title}<ChevronDown aria-hidden="true" className="h-3.5 w-3.5 shrink-0 transition-transform group-open/disclosure:rotate-180" />
      </summary>
      <div className="border-t border-as-border/60 px-4 py-4 text-sm leading-7 text-as-muted">{children}</div>
    </details>
  );
}
