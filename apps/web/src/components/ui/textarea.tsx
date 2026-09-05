"use client";

import { cn } from "@/lib/utils";

export function Textarea({
  className,
  value,
  onChange,
  placeholder,
  disabled,
  rows = 4,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { className?: string }) {
  return (
    <textarea
      className={cn(
        "w-full rounded-as border border-as-border bg-as-bg p-3 text-as-text placeholder:text-as-muted focus:border-as-primary focus:ring-1 focus:ring-as-primary transition-colors resize-y",
        className,
      )}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      disabled={disabled}
      rows={rows}
      {...props}
    />
  );
}
