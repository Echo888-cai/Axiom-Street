import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface PanelProps {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  /** Remove default body padding for charts/tables that manage their own */
  flush?: boolean;
}

/**
 * The fundamental workspace surface. One hairline border, quiet header,
 * no shadows, no gradients.
 */
export function Panel({
  title,
  subtitle,
  actions,
  children,
  className,
  bodyClassName,
  flush,
}: PanelProps) {
  return (
    <section
      className={cn(
        "flex min-h-0 flex-col rounded-lg border border-edge bg-panel",
        className,
      )}
    >
      {(title || actions) && (
        <header className="flex h-10 shrink-0 items-center justify-between gap-3 border-b border-edge px-3.5">
          <div className="flex min-w-0 items-baseline gap-2">
            {title && (
              <h3 className="truncate text-[13px] font-medium text-text">
                {title}
              </h3>
            )}
            {subtitle && (
              <span className="truncate text-xs text-text-3">{subtitle}</span>
            )}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-1">{actions}</div>}
        </header>
      )}
      <div className={cn("min-h-0 flex-1", !flush && "p-3.5", bodyClassName)}>
        {children}
      </div>
    </section>
  );
}
