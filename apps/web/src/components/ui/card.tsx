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
        "as-card rounded-as border border-as-border bg-as-bg p-5 sm:p-6 shadow-as",
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
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 className="text-[14px] font-semibold tracking-tight text-as-text">
          {title}
        </h3>
        {hint ? <div className="mt-0.5">{hint}</div> : null}
      </div>
      {action}
    </div>
  );
}

export function CardTitle({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <h3
      className={cn(
        "text-[14px] font-semibold tracking-tight text-as-text",
        className,
      )}
    >
      {children}
    </h3>
  );
}

export function CardContent({
  className,
  children,
}: {
  className?: string;
  children?: React.ReactNode;
}) {
  return <div className={cn("", className)}>{children}</div>;
}
