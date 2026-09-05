"use client";

import { cn } from "@/lib/utils";

interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "destructive" | "success" | "warning";
}

export function Alert({
  className,
  variant = "default",
  children,
  ...props
}: AlertProps) {
  return (
    <div
      className={cn(
        "rounded-as border p-4",
        variant === "default" && "border-as-border bg-as-bg",
        variant === "destructive" &&
          "border-as-negative/30 bg-as-negative/5 text-as-negative",
        variant === "success" &&
          "border-as-positive/30 bg-as-positive/5 text-as-positive",
        variant === "warning" &&
          "border-yellow-500/30 bg-yellow-500/5 text-yellow-700",
        className,
      )}
      role="alert"
      {...props}
    >
      {children}
    </div>
  );
}

export function AlertDescription({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn("text-sm", className)} {...props}>
      {children}
    </p>
  );
}
