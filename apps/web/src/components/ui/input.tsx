import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(function Input({ className, ...props }, ref) {
  return (
    <input
      ref={ref}
      className={cn(
        "h-11 rounded-xl border border-as-border bg-as-bg shadow-[inset_0_1px_2px_rgba(30,42,62,0.025)] px-3 text-sm text-as-text outline-none transition-colors duration-as",
        "placeholder:text-as-muted",
        "focus:border-as-primary/40 focus:ring-2 focus-visible:ring-as-primary/20",
        className,
      )}
      {...props}
    />
  );
});
