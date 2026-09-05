"use client";

import { cn } from "@/lib/utils";

export function Label({
  className,
  htmlFor,
  children,
  ...props
}: React.LabelHTMLAttributes<HTMLLabelElement> & { className?: string }) {
  return (
    <label
      htmlFor={htmlFor}
      className={cn("text-sm font-medium text-as-text", className)}
      {...props}
    >
      {children}
    </label>
  );
}
