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
