import type { LucideIcon } from "lucide-react";

export function EmptyState({
  title,
  description,
  action,
  icon: Icon,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: LucideIcon;
}) {
  return (
    <div className="flex h-full min-h-[140px] flex-col items-center justify-center px-6 py-10 text-center">
      {Icon ? (
        <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[rgba(22,119,255,0.08)] text-as-primary">
          <Icon className="h-5 w-5" strokeWidth={1.75} />
        </span>
      ) : null}
      <p className="text-sm font-medium tracking-tight text-as-text">{title}</p>
      {description ? (
        <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-as-muted">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
