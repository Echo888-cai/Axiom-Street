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
        "rounded-as border border-as-border bg-as-bg p-5 shadow-as",
        hover &&
          "transition-all duration-as hover:-translate-y-px hover:border-as-primary/25 hover:shadow-as-lg",
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
        <h3 className="text-sm font-medium tracking-tight text-as-text">{title}</h3>
        {hint ? <div className="mt-0.5">{hint}</div> : null}
      </div>
      {action}
    </div>
  );
}
