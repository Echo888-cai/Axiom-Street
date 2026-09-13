"use client";

import { cn } from "@/lib/utils";

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  className?: string;
}

export function Select({ className, children, ...props }: SelectProps) {
  return (
    <select
      className={cn(
        "as-field as-select min-h-11 w-full min-w-0 rounded-xl border border-as-border bg-as-bg px-3 py-2.5 text-sm text-as-text transition-colors",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}

interface SelectTriggerProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  className?: string;
}

export function SelectTrigger({
  className,
  children,
  ...props
}: SelectTriggerProps) {
  return (
    <button
      className={cn(
        "as-field min-h-11 w-full rounded-xl border border-as-border bg-as-bg p-3 text-left text-as-text focus:border-as-primary focus:ring-1 focus:ring-as-primary transition-colors",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function SelectContent({ children }: { children: React.ReactNode }) {
  return <div className="relative z-50">{children}</div>;
}

export function SelectItem({
  value,
  children,
  className,
}: {
  value: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <option value={value} className={className}>
      {children}
    </option>
  );
}

export function SelectValue({ placeholder }: { placeholder?: string }) {
  return <span className="text-as-muted">{placeholder}</span>;
}
