import { cn } from "@/lib/utils";

export function Card({
  className,
  children,
  hover,
}: {
  className?: string;
  children?: React.ReactNode;
  hover?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-aq border border-aq-border bg-aq-bg p-5 shadow-aq",
        hover &&
          "transition-all duration-aq hover:-translate-y-px hover:border-aq-primary/25 hover:shadow-aq-lg",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  action,
  hint,
}: {
  title: string;
  action?: React.ReactNode;
  hint?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h3 className="text-sm font-medium tracking-tight text-aq-text">{title}</h3>
        {hint ? <div className="mt-0.5">{hint}</div> : null}
      </div>
      {action}
    </div>
  );
}
